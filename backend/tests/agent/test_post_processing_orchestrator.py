from app.agent.post_processing_orchestrator import (
    process_approved_response,
)
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    OutputGuardrailResult,
    ProviderErrorType,
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
    VisualizationType,
)
from app.agent.synthesis_orchestrator import SynthesisFlowResult


def _query_result(
    *,
    rows=None,
    row_count=None,
    truncated=False,
):
    rows = rows if rows is not None else [
        ["Recife", 100.0],
        ["Olinda", 80.0],
    ]

    return QueryExecutionResult(
        columns=["municipio", "receita"],
        rows=rows,
        row_count=len(rows) if row_count is None else row_count,
        truncated=truncated,
    )


def _approved_flow():
    synthesis = SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer="Recife possui a maior receita.",
    )

    guardrail = OutputGuardrailResult(
        decision=OutputGuardrailDecision.ALLOW,
        reason=None,
        retryable=False,
        original_answer=synthesis.answer,
    )

    return SynthesisFlowResult(
        synthesis=synthesis,
        guardrail=guardrail,
        provider_attempts=[],
        provider_error=None,
        regenerations=0,
    )


def test_approved_flow_is_post_processed():
    result = process_approved_response(
        flow=_approved_flow(),
        result=_query_result(),
    )

    assert result is not None
    assert result.answer == "Recife possui a maior receita."
    assert result.visualization is not None
    assert result.visualization.type == VisualizationType.BAR


def test_blocked_output_does_not_reach_post_processing():
    synthesis = SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer="Resposta bloqueada.",
    )

    guardrail = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=OutputGuardrailReason.SQL_IN_ANSWER,
        retryable=True,
        original_answer=synthesis.answer,
    )

    flow = SynthesisFlowResult(
        synthesis=synthesis,
        guardrail=guardrail,
        provider_attempts=[],
        provider_error=None,
        regenerations=1,
    )

    result = process_approved_response(
        flow=flow,
        result=_query_result(),
    )

    assert result is None


def test_provider_error_does_not_reach_post_processing():
    flow = SynthesisFlowResult(
        synthesis=None,
        guardrail=None,
        provider_attempts=[],
        provider_error=ProviderErrorType.TIMEOUT,
        regenerations=0,
    )

    result = process_approved_response(
        flow=flow,
        result=_query_result(),
    )

    assert result is None


def test_missing_synthesis_does_not_reach_post_processing():
    flow = SynthesisFlowResult(
        synthesis=None,
        guardrail=None,
        provider_attempts=[],
        provider_error=None,
        regenerations=0,
    )

    result = process_approved_response(
        flow=flow,
        result=_query_result(),
    )

    assert result is None


def test_no_data_is_approved_without_output_guardrail():
    synthesis = SynthesisResult(
        status=SynthesisStatus.NO_DATA,
        answer="Não encontrei dados para esse filtro.",
    )

    flow = SynthesisFlowResult(
        synthesis=synthesis,
        guardrail=None,
        provider_attempts=[],
        provider_error=None,
        regenerations=0,
    )

    query_result = _query_result(
        rows=[],
        row_count=0,
    )

    result = process_approved_response(
        flow=flow,
        result=query_result,
    )

    assert result is not None
    assert result.answer == "Não encontrei dados para esse filtro."
    assert result.visualization is None