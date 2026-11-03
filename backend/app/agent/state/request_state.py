import asyncio
import logging
from dataclasses import dataclass
from app.core.observability import observe
from enum import Enum

from app.agent.schemas import PostProcessingResult
from app.agent.state.cache_key import build_cache_key
from app.agent.state.cache import read_cache
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.memory_context import build_memory_context


logger = logging.getLogger(__name__)


class MemoryContextStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    EMPTY = "empty"
    LOADED = "loaded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RequestState:
    memory_context: str | None
    cache_key: str | None
    memory_status: MemoryContextStatus
    cached_response: PostProcessingResult | None = None

    @property
    def cache_hit(self) -> bool:
        return self.cached_response is not None


@observe("C2")
async def prepare_request_state(
    *,
    normalized_question: str,
    session_id: str | None,
    dependencies: AgentStateDependencies,
    memory_context: str | None = None,
) -> RequestState:
    """Recebe a pergunta já aprovada/normalizada pela C1; não executa o agente."""
    memory_status = (
        MemoryContextStatus.LOADED if memory_context is not None
        else MemoryContextStatus.NOT_REQUESTED
    )

    if (
        session_id is not None
        and dependencies.memory_store is not None
    ):
        try:
            async with asyncio.timeout(dependencies.memory_timeout_seconds):
                entries = await dependencies.memory_store.get_context(session_id)
            memory_context = build_memory_context(entries)
            memory_status = (
                MemoryContextStatus.LOADED if memory_context is not None
                else MemoryContextStatus.EMPTY
            )
        except Exception as error:
            logger.warning("Falha ao ler memória. error_type=%s", type(error).__name__)
            memory_context = None
            memory_status = MemoryContextStatus.UNAVAILABLE

    cache_key: str | None = None
    cached_response: PostProcessingResult | None = None

    if (
        dependencies.cache_store is not None
        and memory_status != MemoryContextStatus.UNAVAILABLE
    ):
        assert dependencies.data_version is not None  # Validada na configuração.
        cache_key = build_cache_key(
            normalized_question=normalized_question,
            session_id=session_id,
            memory_context=memory_context,
            data_version=dependencies.data_version,
        )
        cached_response = await read_cache(
            dependencies.cache_store,
            cache_key,
            timeout_seconds=dependencies.cache_timeout_seconds,
        )

    return RequestState(
        memory_context=memory_context,
        cache_key=cache_key,
        memory_status=memory_status,
        cached_response=cached_response,
    )
