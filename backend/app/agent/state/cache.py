from typing import Protocol

from app.agent.schemas import (
    AgentOutcome,
    PostProcessingResult,
)


CACHE_ELIGIBLE_OUTCOMES = {
    AgentOutcome.ANSWERED,
}


class CacheStore(Protocol):
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


def should_store_in_cache(outcome: AgentOutcome) -> bool:
    return outcome in CACHE_ELIGIBLE_OUTCOMES