from dataclasses import dataclass

from app.agent.schemas import PostProcessingResult
from app.agent.state.cache_key import build_cache_key
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.memory_context import build_memory_context


@dataclass(frozen=True, slots=True)
class RequestState:
    memory_context: str | None
    cache_key: str
    cached_response: PostProcessingResult | None = None

    @property
    def cache_hit(self) -> bool:
        return self.cached_response is not None


async def prepare_request_state(
    *,
    question: str,
    session_id: str | None,
    dependencies: AgentStateDependencies,
    data_version: str | None = None,
) -> RequestState:
    memory_context: str | None = None

    if (
        session_id is not None
        and dependencies.memory_store is not None
    ):
        try:
            entries = await dependencies.memory_store.get_context(
                session_id
            )
            memory_context = build_memory_context(entries)
        except Exception:
            memory_context = None

    cache_key = build_cache_key(
        question=question,
        session_id=session_id,
        memory_context=memory_context,
        data_version=data_version,
    )

    cached_response: PostProcessingResult | None = None

    if dependencies.cache_store is not None:
        try:
            cached_response = await dependencies.cache_store.get(
                cache_key
            )
        except Exception:
            cached_response = None

    return RequestState(
        memory_context=memory_context,
        cache_key=cache_key,
        cached_response=cached_response,
    )