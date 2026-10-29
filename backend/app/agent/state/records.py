from app.agent.schemas import (
    AgentOutcome,
    AuditRecord,
    MemoryEntry,
    ProviderErrorType,
    QueryExecutionResult,
)
from app.agent.state.memory import should_store_in_memory


def build_audit_record(
    *,
    request_id: str,
    question: str,
    outcome: AgentOutcome,
    session_id: str | None = None,
    cache_hit: bool = False,
    sql: str | None = None,
    query_result: QueryExecutionResult | None = None,
    provider_error: ProviderErrorType | None = None,
    regenerations: int = 0,
    final_answer: str | None = None,
) -> AuditRecord:
    """
    Monta o registro de auditoria de uma execução do agente.

    Informações sobre linhas e truncamento são derivadas diretamente
    do resultado da consulta quando ele existir.
    """

    return AuditRecord(
        request_id=request_id,
        session_id=session_id,
        question=question,
        outcome=outcome,
        cache_hit=cache_hit,
        sql=sql,
        row_count=(
            query_result.row_count
            if query_result is not None
            else None
        ),
        truncated=(
            query_result.truncated
            if query_result is not None
            else None
        ),
        provider_error=provider_error,
        regenerations=regenerations,
        final_answer=final_answer,
    )


def build_memory_entry(
    *,
    question: str,
    answer: str | None,
    outcome: AgentOutcome,
) -> MemoryEntry | None:
    """
    Cria uma entrada de memória apenas quando o outcome é elegível
    e existe uma resposta útil para preservar.
    """

    if not should_store_in_memory(outcome):
        return None

    if answer is None or not answer.strip():
        return None

    return MemoryEntry(
        question=question,
        answer=answer.strip(),
        outcome=outcome,
    )