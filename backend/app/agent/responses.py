from app.agent.schemas import GuardrailReason


GUARDRAIL_MESSAGES = {
    GuardrailReason.INVALID_INPUT: (
        "Não foi possível identificar uma pergunta válida. "
        "Tente reformular sua solicitação."
    ),

    GuardrailReason.INPUT_TOO_LONG: (
        "Sua pergunta excede o limite de 500 caracteres. "
        "Tente resumi-la antes de enviar novamente."
    ),

    GuardrailReason.DIRECT_SQL: (
        "Este agente foi projetado para receber perguntas em linguagem natural. "
        "Reformule sua solicitação sem comandos SQL."
    ),

    GuardrailReason.URL_NOT_SUPPORTED: (
        "Este agente não acessa links externos. "
        "Faça sua pergunta diretamente com base nos dados da V-Energy."
    ),

    GuardrailReason.PROMPT_INJECTION_PATTERN: (
        "Não foi possível processar essa solicitação porque ela tenta alterar "
        "o comportamento ou as instruções do agente."
    ),

    GuardrailReason.GUARDRAIL_INTERNAL_ERROR: (
        "Não foi possível validar sua solicitação neste momento. "
        "Tente novamente."
    ),
}


DEFAULT_GUARDRAIL_MESSAGE = (
    "Não foi possível processar sua solicitação."
)


def get_guardrail_message(reason: GuardrailReason | None) -> str:
    if reason is None:
        return DEFAULT_GUARDRAIL_MESSAGE

    return GUARDRAIL_MESSAGES.get(
        reason,
        DEFAULT_GUARDRAIL_MESSAGE,
    )