"""Memória curta de sessão. Erro de leitura deve chegar como UNAVAILABLE."""

import asyncio
import hashlib
import logging

from app.agent.schemas import MemoryEntry
from app.agent.state.cache import validate_cache_timeout, validate_cache_ttl
from app.agent.state.memory import (
    DEFAULT_MEMORY_TIMEOUT_SECONDS,
    DEFAULT_MEMORY_TTL_SECONDS,
    should_store_in_memory,
)
from app.agent.state.memory_context import MEMORY_STORAGE_LIMIT
from app.agent.state.redis_client import create_redis_client


MEMORY_KEY_PREFIX = "agent:memory:v2"
logger = logging.getLogger(__name__)


# Evita duplicatas consecutivas mesmo com finalizações concorrentes.
_APPEND_TURN = """
local last = redis.call('LINDEX', KEYS[1], -1)
local duplicate = false
if last then
    local ok, previous = pcall(cjson.decode, last)
    local current = cjson.decode(ARGV[1])
    if ok and type(previous) == 'table' then
        duplicate = previous.question == current.question and previous.answer == current.answer and previous.outcome == current.outcome
    end
end
if not duplicate then redis.call('RPUSH', KEYS[1], ARGV[1]) end
redis.call('LTRIM', KEYS[1], -tonumber(ARGV[2]), -1)
redis.call('EXPIRE', KEYS[1], ARGV[3])
return duplicate and 0 or 1
"""


class CorruptedMemoryError(ValueError):
    """Payload inválido; difere de falhas de conexão/timeout do Redis."""


def build_memory_key(session_id: str) -> str:
    return f"{MEMORY_KEY_PREFIX}:{hashlib.sha256(session_id.encode('utf-8')).hexdigest()}"


class RedisMemoryStore:
    def __init__(
        self, url: str, *, ttl_seconds: int = DEFAULT_MEMORY_TTL_SECONDS,
        timeout_seconds: float = DEFAULT_MEMORY_TIMEOUT_SECONDS,
    ) -> None:
        validate_cache_ttl(ttl_seconds)
        validate_cache_timeout(timeout_seconds)
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._timeout_seconds = timeout_seconds

    async def get_context(self, session_id: str) -> list[MemoryEntry]:
        # Corrupção continua sendo UNAVAILABLE nesta requisição, mesmo após DELETE.
        key = build_memory_key(session_id)
        async with asyncio.timeout(self._timeout_seconds):
            async with create_redis_client(self._url, self._timeout_seconds) as client:
                # Erros de infraestrutura nesta leitura propagam sem apagar a sessão.
                values = await client.lrange(key, -MEMORY_STORAGE_LIMIT, -1)
                try:
                    entries = [MemoryEntry.model_validate_json(value, strict=True) for value in values]
                    if any(not should_store_in_memory(entry.outcome) for entry in entries):
                        raise ValueError("Memória contém outcome incompatível.")
                except ValueError as error:
                    logger.warning("Payload de memória corrompido/incompatível.")
                    try:
                        await client.delete(key)
                    except Exception as cleanup_error:
                        logger.warning(
                            "Falha ao remover memória corrompida. error_type=%s",
                            type(cleanup_error).__name__,
                        )
                    raise CorruptedMemoryError("Payload de memória incompatível.") from error
                if entries:
                    await client.expire(key, self._ttl_seconds)
                return entries

    async def append(self, session_id: str, entry: MemoryEntry) -> None:
        validated = MemoryEntry.model_validate(entry.model_dump(), strict=True)
        if not should_store_in_memory(validated.outcome):
            return
        key = build_memory_key(session_id)
        async with asyncio.timeout(self._timeout_seconds):
            async with create_redis_client(self._url, self._timeout_seconds) as client:
                await client.eval(
                    _APPEND_TURN, 1, key, validated.model_dump_json(exclude_none=True),
                    MEMORY_STORAGE_LIMIT, self._ttl_seconds,
                )
