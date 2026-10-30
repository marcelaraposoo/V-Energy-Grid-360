import pytest

from app.agent.execution_responses import (
    DEFAULT_EXECUTION_MESSAGE,
    EXECUTION_MESSAGES,
    get_execution_message,
)
from app.agent.guardrails.output_text_rules import (
    contains_technical_error,
    mentions_provider_or_model,
)
from app.agent.schemas import SQLExecutionErrorType


@pytest.mark.parametrize("error", list(SQLExecutionErrorType))
def test_every_error_has_a_message(error):
    assert error in EXECUTION_MESSAGES
    assert get_execution_message(error).strip()


def test_none_returns_default_message():
    assert get_execution_message(None) == DEFAULT_EXECUTION_MESSAGE


def test_messages_do_not_expose_internals():
    for error, message in EXECUTION_MESSAGES.items():
        assert not mentions_provider_or_model(message)
        assert not contains_technical_error(message)
        assert error.value not in message