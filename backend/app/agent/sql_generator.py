import re
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

    from app.agent.conversation import financial_clarification, resolve_followup, delta, operational_expenses
    if operational_expenses(question):
        return SQLGenerationResult(status=SQLGenerationStatus.INSUFFICIENT_CONTEXT, reason="Despesas operacionais não estão disponíveis na Gold."), [], None
    clarification = financial_clarification(question, memory_context)
    if clarification:
        return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason=clarification), [], None
    resolved = resolve_followup(question, memory_context)
    if delta(question) and resolved == question:
        return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason="Qual consulta anterior você deseja ajustar? Informe a métrica e o recorte que devem ser mantidos."), [], None
    question = resolved
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

    # Uma janela móvel de 12 meses não representa outra quantidade de meses.
    # Não executar uma interpretação comprovadamente incompatível.
    from sqlglot import parse_one, exp
    period = re.search(r"[uú]ltimos (\d+) meses", question, re.I)
    if output.sql and period and int(period[1]) != 12:
        try:
            columns = list(parse_one(output.sql, read="sqlite").find_all(exp.Column))
            if any(c.name.lower() in {"dec_12m_horas", "fec_12m"} for c in columns):
                return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason="A consulta proposta não corresponde à janela mensal solicitada. Reformule o período para uma nova tentativa."), attempts, None
        except Exception:
            pass  # A C4.2 continua responsável por SQL inválido.
    if output.sql:
        from app.agent.intent_validation import sql_intent_problem
        problem = sql_intent_problem(question, output.sql)
        if problem:
            return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason=problem), attempts, None
    return output, attempts, None
