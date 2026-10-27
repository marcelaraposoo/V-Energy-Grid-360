import pytest

from app.agent.guardrails.output_text_rules import (
    contains_technical_error,
    mentions_provider_or_model,
)
from app.agent.output_responses import (
    DEFAULT_OUTPUT_MESSAGE,
    OUTPUT_GUARDRAIL_MESSAGES,
    get_output_guardrail_message,
)
from app.agent.schemas import OutputGuardrailReason


@pytest.mark.parametrize("reason", list(OutputGuardrailReason))
def test_every_reason_has_a_message(reason):
    assert reason in OUTPUT_GUARDRAIL_MESSAGES
    assert get_output_guardrail_message(reason).strip()


def test_none_returns_default_message():
    assert (
        get_output_guardrail_message(None)
        == DEFAULT_OUTPUT_MESSAGE
    )


def test_messages_do_not_expose_internals():
    for reason, message in OUTPUT_GUARDRAIL_MESSAGES.items():
        assert not mentions_provider_or_model(message)
        assert not contains_technical_error(message)
        assert reason.value not in message