"""Memória curta de sessão. Erro de leitura deve chegar como UNAVAILABLE."""

import asyncio
import hashlib

from app.agent.schemas import MemoryEntry
from app.agent.state.cache import validate_cache_timeout, validate_cache_ttl
from app.agent.state.memory import (
    DEFAULT_MEMORY_TIMEOUT_SECONDS,
    DEFAULT_MEMORY_TTL_SECONDS,
    should_store_in_memory,
)
from app.agent.state.memory_context import MEMORY_STORAGE_LIMIT
from app.agent.state.redis_client import create_redis_client


MEMORY_KEY_PREFIX = "agent:memory:v1"


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
        # Não converte falha/payload incompatível em memória vazia.
        async with asyncio.timeout(self._timeout_seconds):
            async with create_redis_client(self._url, self._timeout_seconds) as client:
                values = await client.lrange(build_memory_key(session_id), -MEMORY_STORAGE_LIMIT, -1)
            entries = [MemoryEntry.model_validate_json(value, strict=True) for value in values]
            if any(not should_store_in_memory(entry.outcome) for entry in entries):
                raise ValueError("Memória contém outcome incompatível.")
            return entries

    async def append(self, session_id: str, entry: MemoryEntry) -> None:
        validated = MemoryEntry.model_validate(entry.model_dump(), strict=True)
        if not should_store_in_memory(validated.outcome):
            return
        key = build_memory_key(session_id)
        async with asyncio.timeout(self._timeout_seconds):
            async with create_redis_client(self._url, self._timeout_seconds) as client:
                # Transação mantém append, limite e renovação do TTL juntos.
                async with client.pipeline(transaction=True) as transaction:
                    transaction.rpush(key, validated.model_dump_json())
                    transaction.ltrim(key, -MEMORY_STORAGE_LIMIT, -1)
                    transaction.expire(key, self._ttl_seconds)
                    await transaction.execute()
