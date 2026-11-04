from typing import Protocol

from app.agent.schemas import AgentOutcome, MemoryEntry


MEMORY_ELIGIBLE_OUTCOMES = {
    AgentOutcome.ANSWERED,
    AgentOutcome.NO_DATA,
    AgentOutcome.OUTPUT_BLOCKED,
    AgentOutcome.INSUFFICIENT_CONTEXT,
    AgentOutcome.NEEDS_CLARIFICATION,
}

DEFAULT_MEMORY_TTL_SECONDS = 86400
DEFAULT_MEMORY_TIMEOUT_SECONDS = 1.0


class MemoryStore(Protocol):
    async def get_context(
        self,
        session_id: str,
    ) -> list[MemoryEntry]:
        ...

    async def append(
        self,
        session_id: str,
        entry: MemoryEntry,
    ) -> None:
        ...


def should_store_in_memory(outcome: AgentOutcome) -> bool:
    return outcome in MEMORY_ELIGIBLE_OUTCOMES
