import re

from app.agent.guardrails.sql_guardrail import (
    build_retry_feedback,
    validate_sql,
)
from app.agent.schemas import (
    ProviderAttempt,
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


async def generate_validate_and_execute(
    question: str,
    database_context: str,
    memory_context: str | None = None,
    *,
    database_path: str | None = None,
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

        provider_attempts.extend(attempts)

        if provider_error is not None:
            return SQLExecutionFlowResult(
                provider_error=provider_error,
                regenerations=regenerations,
            )

        if generation is None:
            return SQLExecutionFlowResult(
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
            )

        if generation.status != SQLGenerationStatus.READY:
            return SQLExecutionFlowResult(
                generation_status=generation.status,
                generation_reason=generation.reason,
                regenerations=regenerations,
            )

        if not generation.sql:
            return SQLExecutionFlowResult(
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
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
                )

            feedback = retry_feedback
            regenerations += 1
            continue

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

        return SQLExecutionFlowResult(
            generation_status=generation.status,
            sql=generation.sql,
            outcome=outcome,
            regenerations=regenerations,
        )