"""Cliente por operação, compatível com asyncio.run por requisição."""

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff


def create_redis_client(url: str, timeout_seconds: float) -> Redis:
    return Redis.from_url(
        url,
        socket_connect_timeout=timeout_seconds,
        socket_timeout=timeout_seconds,
        retry=Retry(NoBackoff(), 0),
    )
