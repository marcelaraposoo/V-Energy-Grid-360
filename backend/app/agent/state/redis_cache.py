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


class RedisCacheStore:
    def __init__(
        self, url: str, *, timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
    ) -> None:
        validate_cache_timeout(timeout_seconds)
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
                    await client.set(key, payload, ex=ttl_seconds)
        except Exception as error:
            logger.warning("Falha Redis SET. error_type=%s", type(error).__name__)
