from app.agent.schemas import (
    AgentOutcome,
    PostProcessingResult,
    ProviderErrorType,
    QueryExecutionResult,
    AuditStep,
    ProviderAttempt,
    SemanticIntent,
)
from app.agent.state.audit import AuditStore
from app.agent.state.cache import (
    CacheStore,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CACHE_TIMEOUT_SECONDS,
)
from app.agent.state.finalizer import finalize
from app.agent.state.memory import MemoryStore, DEFAULT_MEMORY_TIMEOUT_SECONDS
from app.agent.state.records import (
    build_audit_record,
    build_memory_entry,
)


async def finalize_request(
    *,
    audit_store: AuditStore | None,
    request_id: str,
    question: str,
    outcome: AgentOutcome,
    session_id: str | None = None,
    final_answer: str | None = None,
    sql: str | None = None,
    query_result: QueryExecutionResult | None = None,
    provider_error: ProviderErrorType | None = None,
    regenerations: int = 0,
    cache_hit: bool = False,
    memory_store: MemoryStore | None = None,
    cache_store: CacheStore | None = None,
    cache_key: str | None = None,
    cache_value: PostProcessingResult | None = None,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    cache_timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
    cache_data_version: str | None = None,
    cache_response_complete: bool = False,
    memory_timeout_seconds: float = DEFAULT_MEMORY_TIMEOUT_SECONDS,
    stage: str | None = None,
    duration_ms: float | None = None,
    provider_attempts: tuple[ProviderAttempt, ...] = (),
    steps: tuple[AuditStep, ...] = (),
    interpretation: SemanticIntent | None = None,
    context_recorded: bool = False,
    context_before: str | None = None,
) -> bool | None:
    """
    Ponte entre o fluxo do agente e a Camada 7.

    Constrói os registros necessários e delega a persistência
    para o Finalizer.
    """

    audit_record = build_audit_record(
        request_id=request_id,
        session_id=session_id,
        question=question,
        outcome=outcome,
        cache_hit=cache_hit,
        sql=sql,
        query_result=query_result,
        provider_error=provider_error,
        regenerations=regenerations,
        final_answer=final_answer,
        stage=stage,
        duration_ms=duration_ms,
        provider_attempts=provider_attempts,
        steps=steps,
    )

    memory_entry = build_memory_entry(
        question=question,
        answer=final_answer,
        outcome=outcome,
    )
    if memory_entry is not None:
        memory_entry.interpretation = interpretation
        memory_entry.context_recorded = context_recorded
        memory_entry.context_before = context_before

    return await finalize(
        audit_store=audit_store,
        audit_record=audit_record,
        memory_store=memory_store,
        memory_entry=memory_entry,
        cache_store=cache_store,
        cache_key=cache_key,
        cache_value=cache_value,
        cache_ttl_seconds=cache_ttl_seconds,
        cache_timeout_seconds=cache_timeout_seconds,
        cache_data_version=cache_data_version,
        cache_response_complete=cache_response_complete,
        memory_timeout_seconds=memory_timeout_seconds,
    )
