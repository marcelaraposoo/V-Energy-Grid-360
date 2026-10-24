import pytest

from app.agent.responses import (
    DEFAULT_GUARDRAIL_MESSAGE,
    GUARDRAIL_MESSAGES,
    get_guardrail_message,
)

from app.agent.schemas import GuardrailReason


@pytest.mark.parametrize(
    ("reason", "expected_text"),
    [
        (
            GuardrailReason.INVALID_INPUT,
            "Não foi possível identificar uma pergunta válida.",
        ),
        (
            GuardrailReason.INPUT_TOO_LONG,
            "Sua pergunta excede o limite de 500 caracteres.",
        ),
        (
            GuardrailReason.DIRECT_SQL,
            "Este agente foi projetado para receber perguntas em linguagem natural.",
        ),
        (
            GuardrailReason.URL_NOT_SUPPORTED,
            "Este agente não acessa links externos.",
        ),
        (
            GuardrailReason.PROMPT_INJECTION_PATTERN,
            "Não foi possível processar essa solicitação",
        ),
        (
            GuardrailReason.GUARDRAIL_INTERNAL_ERROR,
            "Não foi possível validar sua solicitação neste momento.",
        ),
    ],
)
def test_returns_correct_message_for_each_reason(
    reason,
    expected_text,
):
    message = get_guardrail_message(reason)

    assert isinstance(message, str)
    assert expected_text in message


def test_returns_default_message_when_reason_is_none():
    message = get_guardrail_message(None)

    assert message == DEFAULT_GUARDRAIL_MESSAGE


def test_all_guardrail_reasons_have_a_message():

    for reason in GuardrailReason:
        assert reason in GUARDRAIL_MESSAGES


def test_all_messages_are_non_empty_strings():
    for message in GUARDRAIL_MESSAGES.values():
        assert isinstance(message, str)
        assert message.strip()


def test_default_message_is_not_empty():
    assert isinstance(DEFAULT_GUARDRAIL_MESSAGE, str)
    assert DEFAULT_GUARDRAIL_MESSAGE.strip()