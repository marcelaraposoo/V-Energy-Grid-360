from dataclasses import dataclass

from app.agent.guardrails.sql_guardrail import (
    build_retry_feedback,
    validate_sql,
)
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    SQLGenerationResult,
    SQLGenerationStatus,
    SQLGuardrailDecision,
    SQLGuardrailResult,
)
from app.agent.sql_generator import generate_sql


MAX_GUARDRAIL_REGENERATIONS = 1


@dataclass(frozen=True)
class SQLGenerationFlowResult:
    generation: SQLGenerationResult | None
    guardrail: SQLGuardrailResult | None
    provider_attempts: list[ProviderAttempt]
    provider_error: ProviderErrorType | None
    regenerations: int


async def generate_and_validate_sql(
    question: str,
    database_context: str,
    memory_context: str | None = None,
) -> SQLGenerationFlowResult:
    """
    Orquestra as etapas 4.1 e 4.2.

    Fluxo:
    1. gera SQL;
    2. valida no SQL Guardrail;
    3. se bloqueado e retryable, permite no máximo
       uma regeneração;
    4. valida novamente;
    5. encerra independentemente do resultado da
       segunda validação.

    O fallback entre providers continua sendo
    responsabilidade de generate_sql()/router.py.
    """

    provider_attempts: list[ProviderAttempt] = []
    regenerations = 0
    guardrail_feedback: str | None = None

    while True:
        generation, attempts, provider_error = (
            await generate_sql(
                question=question,
                database_context=database_context,
                memory_context=memory_context,
                guardrail_feedback=guardrail_feedback,
            )
        )

        provider_attempts.extend(attempts)

        if provider_error is not None:
            return SQLGenerationFlowResult(
                generation=None,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=provider_error,
                regenerations=regenerations,
            )

        if generation is None:
            return SQLGenerationFlowResult(
                generation=None,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
            )

        if generation.status != SQLGenerationStatus.READY:
            return SQLGenerationFlowResult(
                generation=generation,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        if not generation.sql:
            return SQLGenerationFlowResult(
                generation=None,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
            )

        guardrail_result = validate_sql(
            generation.sql
        )

        if (
            guardrail_result.decision
            == SQLGuardrailDecision.ALLOW
        ):
            return SQLGenerationFlowResult(
                generation=generation,
                guardrail=guardrail_result,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        if not guardrail_result.retryable:
            return SQLGenerationFlowResult(
                generation=generation,
                guardrail=guardrail_result,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        if (
            regenerations
            >= MAX_GUARDRAIL_REGENERATIONS
        ):
            return SQLGenerationFlowResult(
                generation=generation,
                guardrail=guardrail_result,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        feedback = build_retry_feedback(
            guardrail_result
        )

        if feedback is None:
            return SQLGenerationFlowResult(
                generation=generation,
                guardrail=guardrail_result,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        guardrail_feedback = feedback
        regenerations += 1