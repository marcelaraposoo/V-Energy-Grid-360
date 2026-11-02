import asyncio
import logging
import math
from typing import Protocol

from app.agent.schemas import (
    AgentOutcome,
    PostProcessingResult,
)


CACHE_ELIGIBLE_OUTCOMES = {
    AgentOutcome.ANSWERED,
}

DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_CACHE_TIMEOUT_SECONDS = 1.0
logger = logging.getLogger(__name__)


def validate_cache_ttl(ttl_seconds: int) -> None:
    if type(ttl_seconds) is not int or ttl_seconds <= 0:
        raise ValueError("cache_ttl_seconds deve ser um inteiro maior que zero.")


def validate_cache_timeout(timeout_seconds: float) -> None:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise ValueError("cache_timeout_seconds deve ser positivo e finito.")


def serialize_cache_value(value: PostProcessingResult) -> str:
    """JSON do contrato atual, sem migração ou reparo de payloads antigos."""
    validated = PostProcessingResult.model_validate(value.model_dump(), strict=True)
    return validated.model_dump_json()


def deserialize_cache_value(payload: str | bytes) -> PostProcessingResult | None:
    """O adapter deve usar validação Pydantic; JSON incompatível é MISS."""
    try:
        return PostProcessingResult.model_validate_json(payload, strict=True)
    except (ValueError, TypeError):
        return None


class CacheStore(Protocol):
    """Contrato do cache; a implementação Redis está em redis_cache.py.

    Persistir JSON com TTL, revalidar via Pydantic no GET e devolver None para
    payload inválido. Operações devem ser assíncronas, respeitar cancelamento
    e ter timeout de conexão/operação finito. Os helpers também limitam a espera.
    """
    async def get(
        self,
        key: str,
    ) -> PostProcessingResult | None:
        ...

    async def set(
        self,
        key: str,
        value: PostProcessingResult,
        ttl_seconds: int,
    ) -> None:
        ...


def should_store_in_cache(
    outcome: AgentOutcome,
    *,
    truncated: bool | None = False,
    response_complete: bool = True,
) -> bool:
    return (
        outcome in CACHE_ELIGIBLE_OUTCOMES
        and truncated is False
        and response_complete is True
    )


async def read_cache(
    store: CacheStore,
    key: str,
    *,
    timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
) -> PostProcessingResult | None:
    try:
        validate_cache_timeout(timeout_seconds)
        async with asyncio.timeout(timeout_seconds):
            value = await store.get(key)
        if not isinstance(value, PostProcessingResult):
            return None
        # Defende também contra stores incorretos e modelos construídos sem validação.
        return PostProcessingResult.model_validate(value.model_dump(), strict=True)
    except Exception as error:
        logger.warning("Falha ao ler cache. error_type=%s", type(error).__name__)
        return None


async def write_cache(
    store: CacheStore,
    key: str,
    value: PostProcessingResult,
    *,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
) -> None:
    try:
        validate_cache_ttl(ttl_seconds)
        validate_cache_timeout(timeout_seconds)
        validated = PostProcessingResult.model_validate(value.model_dump(), strict=True)
        async with asyncio.timeout(timeout_seconds):
            await store.set(key, validated, ttl_seconds)
    except Exception as error:
        logger.warning("Falha ao persistir cache. error_type=%s", type(error).__name__)
