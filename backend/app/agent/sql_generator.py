from app.agent.prompts.sql_generation.loader import (
    load_sql_generation_prompts,
)
from app.agent.providers.router import run_with_fallback
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    SQLGenerationResult,
    SQLGenerationStatus,
)


def build_sql_generation_prompt(
    question: str,
    database_context: str,
    memory_context: str | None = None,
    guardrail_feedback: str | None = None,
) -> str:
    """
    Monta o conteúdo dinâmico enviado à etapa 4.1.

    As regras fixas ficam nos arquivos Markdown.
    Aqui entram apenas os dados específicos da solicitação.
    """

    memory = (
        memory_context.strip()
        if memory_context and memory_context.strip()
        else "Nenhum contexto recente disponível."
    )

    feedback_section = ""

    if guardrail_feedback and guardrail_feedback.strip():
        feedback_section = (
            "\n\n<guardrail_feedback>\n"
            f"{guardrail_feedback.strip()}\n"
            "</guardrail_feedback>"
        )

    return (
        "<user_question>\n"
        f"{question}\n"
        "</user_question>\n\n"
        "<conversation_context>\n"
        f"{memory}\n"
        "</conversation_context>\n\n"
        "<database_context>\n"
        f"{database_context}\n"
        "</database_context>"
        f"{feedback_section}"
    )


async def generate_sql(
    question: str,
    database_context: str,
    memory_context: str | None = None,
    guardrail_feedback: str | None = None,
) -> tuple[
    SQLGenerationResult | None,
    list[ProviderAttempt],
    ProviderErrorType | None,
]:
    """
    Executa a etapa 4.1 do agente.

    Responsabilidades:
    - interpretar a pergunta;
    - avaliar domínio e segurança semanticamente;
    - considerar a memória recente;
    - considerar feedback interno do SQL Guardrail;
    - gerar uma proposta de SQL estruturada.

    Esta função NÃO executa SQL.
    """

    if not database_context.strip():
        result = SQLGenerationResult(
            status=SQLGenerationStatus.INSUFFICIENT_CONTEXT,
            sql=None,
            reason=(
                "O contexto do banco de dados não possui "
                "informações suficientes para gerar a consulta."
            ),
        )

        return result, [], None

    instructions = load_sql_generation_prompts()

    prompt = build_sql_generation_prompt(
        question=question,
        database_context=database_context,
        memory_context=memory_context,
        guardrail_feedback=guardrail_feedback,
    )

    output, attempts, error = await run_with_fallback(
        prompt,
        output_type=SQLGenerationResult,
        instructions=instructions,
    )

    if error is not None:
        return None, attempts, error

    if not isinstance(
        output,
        SQLGenerationResult,
    ):
        return (
            None,
            attempts,
            ProviderErrorType.INVALID_OUTPUT,
        )

    return output, attempts, None