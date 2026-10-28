from dataclasses import dataclass

from app.agent.answer_synthesizer import synthesize_answer
from app.agent.guardrails.output_guardrail import (
    build_output_retry_feedback,
    validate_output,
)
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailResult,
    ProviderAttempt,
    ProviderErrorType,
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
)


MAX_OUTPUT_REGENERATIONS = 1


@dataclass(frozen=True)
class SynthesisFlowResult:
    synthesis: SynthesisResult | None
    guardrail: OutputGuardrailResult | None
    provider_attempts: list[ProviderAttempt]
    provider_error: ProviderErrorType | None
    regenerations: int

    @property
    def approved(self) -> bool:
        """
        True quando a resposta pode ser exibida ao usuário.

        Resultado vazio (NO_DATA) é uma mensagem fixa em código e
        não passa pelo guardrail. Qualquer outra resposta só é
        aprovada com ALLOW.
        """

        if self.synthesis is None:
            return False

        if self.guardrail is None:
            return self.synthesis.status == SynthesisStatus.NO_DATA

        return (
            self.guardrail.decision
            == OutputGuardrailDecision.ALLOW
        )


async def synthesize_and_validate(
    question: str,
    sql: str,
    result: QueryExecutionResult,
) -> SynthesisFlowResult:
    """
    Orquestra a 4.4 (síntese) e a Camada 5 (Output Guardrail).

    Fluxo:
    1. sintetiza a resposta;
    2. valida no Output Guardrail;
    3. se bloqueada e retryable, permite no máximo uma
       regeneração, com feedback;
    4. valida novamente;
    5. encerra independentemente do resultado.

    O chamador só deve exibir synthesis.answer quando
    approved for True. Caso contrário, use
    get_provider_message() (erro de provider) ou
    get_output_guardrail_message() (resposta bloqueada).
    """

    provider_attempts: list[ProviderAttempt] = []
    regenerations = 0
    feedback: str | None = None

    while True:
        synthesis, attempts, provider_error = (
            await synthesize_answer(
                question=question,
                sql=sql,
                result=result,
                guardrail_feedback=feedback,
            )
        )

        provider_attempts.extend(attempts)

        if provider_error is not None:
            return SynthesisFlowResult(
                synthesis=None,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=provider_error,
                regenerations=regenerations,
            )

        if synthesis is None:
            return SynthesisFlowResult(
                synthesis=None,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=ProviderErrorType.INVALID_OUTPUT,
                regenerations=regenerations,
            )

        if synthesis.status == SynthesisStatus.NO_DATA:
            return SynthesisFlowResult(
                synthesis=synthesis,
                guardrail=None,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        guardrail = validate_output(
            answer=synthesis.answer,
            assumptions=synthesis.assumptions,
            question=question,
            sql=sql,
            result=result,
        )

        if (
            guardrail.decision == OutputGuardrailDecision.ALLOW
            or not guardrail.retryable
            or regenerations >= MAX_OUTPUT_REGENERATIONS
        ):
            return SynthesisFlowResult(
                synthesis=synthesis,
                guardrail=guardrail,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        retry_feedback = build_output_retry_feedback(guardrail)

        if retry_feedback is None:
            return SynthesisFlowResult(
                synthesis=synthesis,
                guardrail=guardrail,
                provider_attempts=provider_attempts,
                provider_error=None,
                regenerations=regenerations,
            )

        feedback = retry_feedback
        regenerations += 1