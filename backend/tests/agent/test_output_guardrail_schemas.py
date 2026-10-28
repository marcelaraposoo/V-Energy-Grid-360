import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    OutputGuardrailResult,
)


def test_allow_result_is_clean():
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.ALLOW,
        original_answer="Resposta.",
    )

    assert result.reason is None
    assert result.retryable is False
    assert result.unsupported_values == []


def test_block_with_unsupported_numbers():
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=OutputGuardrailReason.UNSUPPORTED_NUMBER,
        retryable=True,
        original_answer="A receita foi 9.999.",
        unsupported_values=["9.999"],
    )

    assert result.unsupported_values == ["9.999"]
    assert result.retryable is True


def test_block_without_unsupported_values_is_valid():
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=OutputGuardrailReason.URL_IN_ANSWER,
        retryable=True,
        original_answer="Veja https://exemplo.com",
    )

    assert result.unsupported_values == []


def test_allow_cannot_have_reason():
    with pytest.raises(ValidationError):
        OutputGuardrailResult(
            decision=OutputGuardrailDecision.ALLOW,
            reason=OutputGuardrailReason.PROMPT_LEAK,
            original_answer="Resposta.",
        )


def test_allow_cannot_be_retryable():
    with pytest.raises(ValidationError):
        OutputGuardrailResult(
            decision=OutputGuardrailDecision.ALLOW,
            retryable=True,
            original_answer="Resposta.",
        )


def test_allow_cannot_have_unsupported_values():
    with pytest.raises(ValidationError):
        OutputGuardrailResult(
            decision=OutputGuardrailDecision.ALLOW,
            original_answer="Resposta.",
            unsupported_values=["1"],
        )


def test_block_requires_reason():
    with pytest.raises(ValidationError):
        OutputGuardrailResult(
            decision=OutputGuardrailDecision.BLOCK,
            original_answer="Resposta.",
        )


def test_unsupported_values_require_unsupported_number_reason():
    with pytest.raises(ValidationError):
        OutputGuardrailResult(
            decision=OutputGuardrailDecision.BLOCK,
            reason=OutputGuardrailReason.PROMPT_LEAK,
            original_answer="Resposta.",
            unsupported_values=["1"],
        )