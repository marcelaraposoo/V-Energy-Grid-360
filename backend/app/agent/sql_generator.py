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
) -> str:

    memory = (
        memory_context.strip()
        if memory_context and memory_context.strip()
        else "Nenhum contexto recente disponível."
    )

    return f"""
<user_question>
{question}
</user_question>

<conversation_context>
{memory}
</conversation_context>

<database_context>
{database_context}
</database_context>
""".strip()


async def generate_sql(
    question: str,
    database_context: str,
    memory_context: str | None = None,
) -> tuple[
    SQLGenerationResult | None,
    list[ProviderAttempt],
    ProviderErrorType | None,
]:

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