import json
from typing import Any

from app.agent.prompts.synthesis.loader import (
    load_synthesis_prompts,
)
from app.agent.providers.router import run_with_fallback
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
)


MAX_ROWS_IN_PROMPT = 50

NO_DATA_MESSAGE = (
    "Não encontrei dados para essa consulta com os filtros "
    "aplicados. Tente ajustar o período, o município ou a "
    "classe de consumo."
)


def _to_safe_json(value: Any) -> str:
    """
    Serializa para JSON e neutraliza o caractere '<'.

    Evita que um valor vindo do banco feche as tags do prompt
    (ex.: '</query_result>') e escape da área de dados.
    O JSON continua válido: \\u003c representa '<'.
    """

    text = json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    )

    return text.replace("<", "\\u003c")


def build_synthesis_prompt(
    question: str,
    sql: str,
    result: QueryExecutionResult,
) -> str:
    """
    Monta o conteúdo dinâmico enviado à etapa 4.4.

    As regras fixas ficam nos arquivos Markdown.
    Aqui entram apenas a pergunta, o SQL e o resultado.
    """

    rows_shown = result.rows[:MAX_ROWS_IN_PROMPT]

    is_partial = (
        result.truncated
        or result.row_count > len(rows_shown)
    )

    payload = {
        "columns": result.columns,
        "rows": rows_shown,
        "row_count": result.row_count,
        "rows_provided": len(rows_shown),
        "truncated": is_partial,
    }

    return (
        "<user_question>\n"
        f"{question}\n"
        "</user_question>\n\n"
        "<executed_sql>\n"
        f"{sql}\n"
        "</executed_sql>\n\n"
        "<query_result>\n"
        f"{_to_safe_json(payload)}\n"
        "</query_result>"
    )


async def synthesize_answer(
    question: str,
    sql: str,
    result: QueryExecutionResult,
) -> tuple[
    SynthesisResult | None,
    list[ProviderAttempt],
    ProviderErrorType | None,
]:
    """
    Executa a etapa 4.4 do agente.

    Responsabilidades:
    - tratar resultado vazio sem chamar a IA;
    - montar o prompt com pergunta, SQL e resultado;
    - pedir ao modelo uma resposta estruturada e fiel aos dados.

    Esta função NÃO executa SQL.
    """

    if result.row_count == 0 and not result.rows:
        no_data = SynthesisResult(
            status=SynthesisStatus.NO_DATA,
            answer=NO_DATA_MESSAGE,
        )

        return no_data, [], None

    instructions = load_synthesis_prompts()

    prompt = build_synthesis_prompt(
        question=question,
        sql=sql,
        result=result,
    )

    output, attempts, error = await run_with_fallback(
        prompt,
        output_type=SynthesisResult,
        instructions=instructions,
    )

    if error is not None:
        return None, attempts, error

    if not isinstance(output, SynthesisResult):
        return (
            None,
            attempts,
            ProviderErrorType.INVALID_OUTPUT,
        )

    return output, attempts, None