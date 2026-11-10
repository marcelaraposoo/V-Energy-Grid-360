from app.core.observability import observe
from app.agent.prompts.sql_generation.loader import (
    load_sql_generation_prompts,
)
from app.agent.providers.router import run_with_fallback
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    SQLGenerationResult,
    SQLGenerationStatus,
    InterpretedRequest,
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
    from app.agent.context.knowledge import knowledge_context

    if guardrail_feedback and guardrail_feedback.strip():
        feedback_section = (
            "\n\n<guardrail_feedback>\n"
            f"{guardrail_feedback.strip()}\n"
            "</guardrail_feedback>"
        )

    return (
        "<user_question>\n"
        f"{question.replace('<', '&lt;')}\n"
        "</user_question>\n\n"
        "<conversation_context>\n"
        f"{memory.replace('<', '&lt;')}\n"
        "</conversation_context>\n\n"
        "<database_context>\n"
        f"{database_context}\n"
        "</database_context>"
        f"{knowledge_context()}"
        f"{feedback_section}"
    )


@observe("C4.1")
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
        output_type=InterpretedRequest,
        instructions=instructions,
    )

    if error is not None:
        return None, attempts, error

    if isinstance(output, InterpretedRequest):
        output = SQLGenerationResult.model_validate(output.model_dump())
    if not isinstance(
        output,
        SQLGenerationResult,
    ):
        return (
            None,
            attempts,
            ProviderErrorType.INVALID_OUTPUT,
        )

    if output.interpretation is not None:
        from app.agent.context.knowledge import source_text
        try:
            source_text(output.interpretation.source_ids)
        except ValueError:
            return None, attempts, ProviderErrorType.INVALID_OUTPUT
    if output.sql and output.interpretation is None:
        from app.agent.intent_validation import sql_intent_problem
        problem = sql_intent_problem(question, output.sql)
        if problem:
            return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason=problem), attempts, None
    return output, attempts, None
