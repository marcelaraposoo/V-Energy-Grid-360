from app.agent.providers.latency_policy import provider_phase
import re
from app.core.observability import observe

from app.agent.pair_check import (
    MUNICIPALITY_MESSAGE,
    clarification_message,
    extract_municipality,
    extract_pair,
    is_empty_or_zero,
    municipality_exists,
    lookup_pair,
)
from app.agent.guardrails.sql_guardrail import (
    build_retry_feedback,
    validate_sql,
)
from app.agent.schemas import (
    ProviderAttempt,
    ProviderPhase,
    ProviderErrorType,
    SQLExecutionErrorType,
    SQLExecutionFlowResult,
    SQLExecutionOutcome,
    SQLGenerationStatus,
    SQLGuardrailDecision,
)
from app.agent.sql_executor import execute_sql
from app.agent.sql_generator import generate_sql


# Orçamento total de regenerações por pergunta, somando os
# bloqueios da 4.2 e os erros de execução da 4.3.
MAX_REGENERATIONS = 1

_REGENERABLE_ERRORS = {
    SQLExecutionErrorType.TABLE_NOT_FOUND,
    SQLExecutionErrorType.COLUMN_NOT_FOUND,
}

_MISSING_OBJECT = re.compile(
    r"no such (?:table|column):\s*([\w.\"`\[\]]+)",
    re.IGNORECASE,
)


def build_execution_retry_feedback(
    sql: str,
    outcome: SQLExecutionOutcome,
) -> str | None:
    """
    Feedback para uma regeneração por erro de tabela ou coluna.

    Leva só o NOME do objeto que não existe (que o próprio modelo
    escreveu). O texto do erro do banco não entra no prompt.
    """

    if outcome.error_type not in _REGENERABLE_ERRORS:
        return None

    match = _MISSING_OBJECT.search(outcome.error_detail or "")
    name = match.group(1).strip("\"`[]") if match else None

    kind = (
        "tabela"
        if outcome.error_type == SQLExecutionErrorType.TABLE_NOT_FOUND
        else "coluna"
    )

    problem = (
        f"A {kind} `{name}` não existe no banco."
        if name
        else f"Uma {kind} usada na consulta não existe no banco."
    )

    return (
        "A consulta SQL anterior falhou ao ser executada.\n\n"
        "SQL anterior:\n"
        f"{sql}\n\n"
        "Motivo:\n"
        f"{problem} Use apenas as tabelas e colunas listadas no "
        "contexto do banco.\n\n"
        "Gere uma nova consulta corrigida, mantendo a intenção "
        "original do usuário e respeitando todas as regras da "
        "etapa de geração SQL."
    )


@observe("sql_flow")
@provider_phase("sql")
async def generate_validate_and_execute(
    question: str,
    database_context: str,
    memory_context: str | None = None,
    *,
    database_path: str | None = None,
    cache_lookup=None,
) -> SQLExecutionFlowResult:
    """
    Orquestra as etapas 4.1, 4.2 e 4.3.

    No máximo UMA regeneração no total: quem precisar primeiro
    (bloqueio da 4.2 ou erro de tabela/coluna da 4.3) usa o
    orçamento, e o resto do fluxo segue sem regenerar.
    """

    provider_attempts: list[ProviderAttempt] = []
    regenerations = 0
    feedback: str | None = None

    while True:
        generation, attempts, provider_error = await generate_sql(
            question=question,
            database_context=database_context,
            memory_context=memory_context,
            guardrail_feedback=feedback,
        )

        provider_attempts.extend(
            item.model_copy(update={"phase": ProviderPhase.SQL_GENERATION, "attempt": index})
            for index, item in enumerate(attempts, len(provider_attempts) + 1)
        )

        if provider_error is not None:
            return SQLExecutionFlowResult(
                provider_error=provider_error,
                regenerations=regenerations,
                provider_attempts=provider_attempts,
            )

        if generation is None:
            return SQLExecutionFlowResult(
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
                provider_attempts=provider_attempts,
            )

        if generation.status != SQLGenerationStatus.READY:
            return SQLExecutionFlowResult(
                generation_status=generation.status,
                generation_reason=generation.reason,
                regenerations=regenerations,
                provider_attempts=provider_attempts,
            )

        if not generation.sql:
            return SQLExecutionFlowResult(
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
                provider_attempts=provider_attempts,
            )

        # ----- 4.2: guardrail do SQL -----
        guardrail = validate_sql(generation.sql)

        if guardrail.decision != SQLGuardrailDecision.ALLOW:
            can_retry = (
                guardrail.retryable
                and regenerations < MAX_REGENERATIONS
            )
            retry_feedback = (
                build_retry_feedback(guardrail) if can_retry else None
            )

            if retry_feedback is None:
                return SQLExecutionFlowResult(
                    generation_status=generation.status,
                    sql=generation.sql,
                    guardrail_reason=guardrail.reason,
                    regenerations=regenerations,
                    provider_attempts=provider_attempts,
                )

            feedback = retry_feedback
            regenerations += 1
            continue

        if cache_lookup is not None:
            try:
                cached = await cache_lookup(generation.sql)
            except Exception:
                from app.agent.state.sql_cache import record_cache
                record_cache("redis_error", "post_sql")
                cached = None
            if cached is not None:
                return SQLExecutionFlowResult(
                    generation_status=generation.status, sql=generation.sql,
                    cached_response=cached, regenerations=regenerations,
                    provider_attempts=provider_attempts,
                )

        # ----- 4.3: execução -----
        kwargs = (
            {"database_path": database_path} if database_path else {}
        )
        outcome = execute_sql(generation.sql, **kwargs)

        if (
            outcome.error_type in _REGENERABLE_ERRORS
            and regenerations < MAX_REGENERATIONS
        ):
            retry_feedback = build_execution_retry_feedback(
                generation.sql, outcome
            )

            if retry_feedback is not None:
                feedback = retry_feedback
                regenerations += 1
                continue

        if outcome.result is not None and is_empty_or_zero(
            outcome.result.columns, outcome.result.rows
        ):
            municipality = extract_municipality(generation.sql)
            if municipality is not None and municipality_exists(
                municipality, database_path
            ) is False:
                return SQLExecutionFlowResult(
                    generation_status=SQLGenerationStatus.NEEDS_CLARIFICATION,
                    generation_reason=MUNICIPALITY_MESSAGE,
                    sql=generation.sql,
                    regenerations=regenerations,
                )

            pair = extract_pair(generation.sql)
            if pair is not None:
                lookup = lookup_pair(*pair, database_path=database_path)
                if lookup is not None and lookup[0] != "exists":
                    return SQLExecutionFlowResult(
                        generation_status=SQLGenerationStatus.NEEDS_CLARIFICATION,
                        generation_reason=clarification_message(
                            lookup[0], None, lookup[1]
                        ),
                        sql=generation.sql,
                        execution_result=outcome.result,
                        execution_elapsed_ms=outcome.elapsed_ms,
                        regenerations=regenerations,
                        provider_attempts=provider_attempts,
                    )

        return SQLExecutionFlowResult(
            generation_status=generation.status,
            sql=generation.sql,
            outcome=outcome,
            execution_result=outcome.result,
            execution_elapsed_ms=outcome.elapsed_ms,
            regenerations=regenerations,
            provider_attempts=provider_attempts,
        )
