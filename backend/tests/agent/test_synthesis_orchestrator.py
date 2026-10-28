import asyncio
from datetime import datetime, timezone

from app.agent import synthesis_orchestrator
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    OutputGuardrailResult,
    ProviderAttempt,
    ProviderErrorType,
    ProviderName,
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
)


QUESTION = "Quantas unidades consumidoras ativas por município?"
SQL = "SELECT municipio, COUNT(*) AS ucs FROM dim_uc GROUP BY municipio"

GOOD = SynthesisResult(
    status=SynthesisStatus.ANSWERED,
    answer="Recife tem 4.820 unidades e Olinda tem 1.310.",
)

BAD = SynthesisResult(
    status=SynthesisStatus.ANSWERED,
    answer="Recife tem 9.999 unidades.",
)

NO_DATA = SynthesisResult(
    status=SynthesisStatus.NO_DATA,
    answer="Não encontrei dados.",
)


def _result():
    return QueryExecutionResult(
        columns=["municipio", "ucs"],
        rows=[["Recife", 4820], ["Olinda", 1310]],
        row_count=2,
    )


def _attempt():
    return ProviderAttempt(
        provider=ProviderName.GEMINI,
        model="modelo-teste",
        attempt=1,
        started_at=datetime.now(timezone.utc),
        success=True,
    )


def _patch_synthesizer(monkeypatch, outputs):
    feedbacks = []

    async def fake_synthesize_answer(
        question, sql, result, guardrail_feedback=None
    ):
        feedbacks.append(guardrail_feedback)
        synthesis, error = outputs[len(feedbacks) - 1]

        return synthesis, [_attempt()], error

    monkeypatch.setattr(
        synthesis_orchestrator,
        "synthesize_answer",
        fake_synthesize_answer,
    )

    return feedbacks


def _run():
    return asyncio.run(
        synthesis_orchestrator.synthesize_and_validate(
            QUESTION, SQL, _result()
        )
    )


def test_max_regenerations_is_one():
    assert synthesis_orchestrator.MAX_OUTPUT_REGENERATIONS == 1


def test_passes_on_first_synthesis(monkeypatch):
    feedbacks = _patch_synthesizer(monkeypatch, [(GOOD, None)])

    flow = _run()

    assert flow.approved is True
    assert flow.synthesis == GOOD
    assert flow.guardrail.decision == OutputGuardrailDecision.ALLOW
    assert flow.regenerations == 0
    assert feedbacks == [None]


def test_retries_once_and_then_passes(monkeypatch):
    feedbacks = _patch_synthesizer(
        monkeypatch, [(BAD, None), (GOOD, None)]
    )

    flow = _run()

    assert flow.approved is True
    assert flow.synthesis == GOOD
    assert flow.regenerations == 1
    assert len(flow.provider_attempts) == 2
    assert feedbacks[0] is None
    assert "9.999" in feedbacks[1]


def test_blocks_after_single_regeneration(monkeypatch):
    feedbacks = _patch_synthesizer(
        monkeypatch, [(BAD, None), (BAD, None)]
    )

    flow = _run()

    assert flow.approved is False
    assert len(feedbacks) == 2
    assert flow.regenerations == 1
    assert flow.guardrail.decision == OutputGuardrailDecision.BLOCK
    assert (
        flow.guardrail.reason
        == OutputGuardrailReason.UNSUPPORTED_NUMBER
    )


def test_no_data_skips_guardrail(monkeypatch):
    feedbacks = _patch_synthesizer(monkeypatch, [(NO_DATA, None)])

    flow = _run()

    assert flow.approved is True
    assert flow.guardrail is None
    assert flow.regenerations == 0
    assert feedbacks == [None]


def test_provider_error_stops_flow(monkeypatch):
    _patch_synthesizer(
        monkeypatch, [(None, ProviderErrorType.RATE_LIMITED)]
    )

    flow = _run()

    assert flow.approved is False
    assert flow.synthesis is None
    assert flow.guardrail is None
    assert flow.provider_error == ProviderErrorType.RATE_LIMITED


def test_provider_error_during_regeneration(monkeypatch):
    _patch_synthesizer(
        monkeypatch,
        [(BAD, None), (None, ProviderErrorType.TIMEOUT)],
    )

    flow = _run()

    assert flow.approved is False
    assert flow.synthesis is None
    assert flow.provider_error == ProviderErrorType.TIMEOUT
    assert flow.regenerations == 1
    assert len(flow.provider_attempts) == 2


def test_missing_synthesis_is_invalid_output(monkeypatch):
    _patch_synthesizer(monkeypatch, [(None, None)])

    flow = _run()

    assert flow.approved is False
    assert flow.provider_error == ProviderErrorType.INVALID_OUTPUT


def test_non_retryable_block_does_not_regenerate(monkeypatch):
    feedbacks = _patch_synthesizer(monkeypatch, [(GOOD, None)])

    monkeypatch.setattr(
        synthesis_orchestrator,
        "validate_output",
        lambda *args, **kwargs: OutputGuardrailResult(
            decision=OutputGuardrailDecision.BLOCK,
            reason=OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR,
            retryable=False,
            original_answer=GOOD.answer,
        ),
    )

    flow = _run()

    assert flow.approved is False
    assert flow.regenerations == 0
    assert len(feedbacks) == 1