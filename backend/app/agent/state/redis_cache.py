"""Cache Redis opcional; falhas nunca impedem a resposta do agente."""

import asyncio
import logging

from redis.asyncio import Redis

from app.agent.schemas import PostProcessingResult
from app.agent.state.redis_client import create_redis_client
from app.agent.state.cache import (
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    deserialize_cache_value,
    serialize_cache_value,
    validate_cache_timeout,
    validate_cache_ttl,
)


logger = logging.getLogger(__name__)


# Um índice técnico por escopo limita todas as versões/perguntas da sessão.
# GET não renova TTL. SET + limpeza + limite são uma única operação atômica.
_BOUNDED_SET = """
local bucket = KEYS[2]
for _, member in ipairs(redis.call('ZRANGE', bucket, 0, -1)) do
    if redis.call('EXISTS', member) == 0 then redis.call('ZREM', bucket, member) end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
local now = redis.call('TIME')
redis.call('ZADD', bucket, tonumber(now[1]) * 1000000 + tonumber(now[2]), KEYS[1])
local excess = redis.call('ZCARD', bucket) - tonumber(ARGV[3])
if excess > 0 then
    local oldest = redis.call('ZRANGE', bucket, 0, excess - 1)
    for _, member in ipairs(oldest) do
        redis.call('DEL', member)
        redis.call('ZREM', bucket, member)
    end
end
local ttl = math.max(tonumber(ARGV[2]), redis.call('TTL', bucket))
redis.call('EXPIRE', bucket, ttl)
return 1
"""


class RedisCacheStore:
    def __init__(
        self, url: str, *, timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
        max_entries_per_session: int = 100,
    ) -> None:
        validate_cache_timeout(timeout_seconds)
        validate_cache_ttl(max_entries_per_session)
        self._max_entries_per_session = max_entries_per_session
        self._url = url
        self._timeout_seconds = timeout_seconds

    def _client(self) -> Redis:
        # O HTTP atual usa asyncio.run por pergunta: não compartilhar pools
        # entre event loops. O contexto de cada operação fecha seu próprio pool.
        return create_redis_client(self._url, self._timeout_seconds)

    async def get(self, key: str) -> PostProcessingResult | None:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    payload = await client.get(key)
                return deserialize_cache_value(payload) if payload is not None else None
        except Exception as error:
            logger.warning("Falha Redis GET. error_type=%s", type(error).__name__)
            return None

    async def set(
        self, key: str, value: PostProcessingResult, ttl_seconds: int,
    ) -> None:
        try:
            validate_cache_ttl(ttl_seconds)
            payload = serialize_cache_value(value)
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    bucket = key.rsplit(":", 1)[0] + ":entries"
                    await client.eval(
                        _BOUNDED_SET, 2, key, bucket, payload,
                        ttl_seconds, self._max_entries_per_session,
                    )
        except Exception as error:
            logger.warning("Falha Redis SET. error_type=%s", type(error).__name__)
