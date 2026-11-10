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
    from app.agent.state.sql_cache import record_cache
    record_cache("cache_disabled" if dependencies.cache_store is None else "not_found_or_expired", "pre_sql")
    memory_status = (
        MemoryContextStatus.LOADED if memory_context is not None
        else MemoryContextStatus.NOT_REQUESTED
    )

    entries = []
    repeated_entry = None
    if (
        session_id is not None
        and dependencies.memory_store is not None
    ):
        try:
            async with asyncio.timeout(dependencies.memory_timeout_seconds):
                entries = await dependencies.memory_store.get_context(session_id)
            if (entries and entries[-1].question == normalized_question
                    and entries[-1].context_recorded
                    and entries[-1].outcome.value == "answered"):
                repeated_entry = entries[-1]
                memory_context = repeated_entry.context_before
            else:
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
        and isinstance(session_id, str) and bool(session_id.strip())
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

    if cache_key is not None and cached_response is None:
        from app.agent.state.cache_eligibility import independent_lookup_key, resolve_intent, intent_digest
        lookup = independent_lookup_key(normalized_question, session_id, dependencies.data_version)
        getter = getattr(dependencies.cache_store, "get_independent", None)
        if lookup is not None and callable(getter):
            try:
                async with asyncio.timeout(dependencies.cache_timeout_seconds):
                    cached_response = await getter(lookup, intent_hash=intent_digest(resolve_intent(normalized_question)))
            except Exception as error:
                logger.warning("Falha ao ler cache independente. error_type=%s", type(error).__name__)

    if (cached_response is not None and repeated_entry is not None
            and cached_response.answer != repeated_entry.answer):
        cached_response = None
        record_cache("context_changed", "pre_sql")
    if cached_response is not None:
        record_cache("hit", "pre_sql", True)
    elif dependencies.cache_store is None:
        record_cache("cache_disabled", "pre_sql")
    elif not session_id or not session_id.strip():
        record_cache("session_missing", "pre_sql")
    elif memory_status == MemoryContextStatus.UNAVAILABLE:
        record_cache("memory_unavailable", "pre_sql")

    return RequestState(
        memory_context=memory_context,
        cache_key=cache_key,
        memory_status=memory_status,
        cached_response=cached_response,
    )
