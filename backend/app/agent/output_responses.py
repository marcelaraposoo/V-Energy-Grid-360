from app.agent.schemas import OutputGuardrailReason


DEFAULT_OUTPUT_MESSAGE = (
    "Não foi possível apresentar uma resposta para essa "
    "pergunta. Tente reformulá-la."
)

_NOT_CONFIRMED_MESSAGE = (
    "Não consegui confirmar todos os valores da resposta nos "
    "dados consultados, então não vou apresentá-la. "
    "Tente reformular a pergunta."
)

_NOT_ADEQUATE_MESSAGE = (
    "Não foi possível gerar uma resposta adequada. "
    "Tente reformular a pergunta de forma mais específica."
)

_INTERNAL_MESSAGE = (
    "Não foi possível validar a resposta neste momento. "
    "Tente novamente."
)


OUTPUT_GUARDRAIL_MESSAGES = {
    OutputGuardrailReason.UNSUPPORTED_NUMBER: (
        _NOT_CONFIRMED_MESSAGE
    ),
    OutputGuardrailReason.EMPTY_ANSWER: _NOT_ADEQUATE_MESSAGE,
    OutputGuardrailReason.ANSWER_TOO_LONG: _NOT_ADEQUATE_MESSAGE,
    OutputGuardrailReason.PROMPT_LEAK: DEFAULT_OUTPUT_MESSAGE,
    OutputGuardrailReason.PROVIDER_DISCLOSURE: (
        DEFAULT_OUTPUT_MESSAGE
    ),
    OutputGuardrailReason.TECHNICAL_ERROR_LEAK: (
        DEFAULT_OUTPUT_MESSAGE
    ),
    OutputGuardrailReason.SQL_IN_ANSWER: DEFAULT_OUTPUT_MESSAGE,
    OutputGuardrailReason.URL_IN_ANSWER: DEFAULT_OUTPUT_MESSAGE,
    OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR: (
        _INTERNAL_MESSAGE
    ),
}


def get_output_guardrail_message(
    reason: OutputGuardrailReason | None,
) -> str:
    if reason is None:
        return DEFAULT_OUTPUT_MESSAGE

    return OUTPUT_GUARDRAIL_MESSAGES.get(
        reason,
        DEFAULT_OUTPUT_MESSAGE,
    )