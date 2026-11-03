import re

import pytest

from app.agent.guardrails.output_guardrail import validate_output
from app.agent.prompts.synthesis.loader import load_synthesis_prompts
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
)


SQL = "SELECT quantidade FROM resumo"


def _result(*, rows=None, truncated=False):
    rows = [[7]] if rows is None else rows
    return QueryExecutionResult(
        columns=["quantidade"],
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )


def test_documented_status_is_accepted_by_synthesis_schema():
    prompt = load_synthesis_prompts()
    match = re.search(r"^- `status`: use sempre `([^`]+)`;", prompt, re.M)

    assert match is not None
    status = match.group(1)
    assert status == SynthesisStatus.ANSWERED.value
    synthesis = SynthesisResult(status=status, answer="Há 7 unidades.")
    assert synthesis.status == SynthesisStatus.ANSWERED


@pytest.mark.parametrize("field", ["answer", "assumptions"])
def test_sql_is_forbidden_even_when_requested_by_user(field):
    prompt = load_synthesis_prompts()
    rule = next(line for line in prompt.splitlines() if "Não revele SQL" in line)
    assert "mesmo quando solicitado" in rule
    assert "a menos que o usuário" not in prompt

    synthesis = SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer=SQL if field == "answer" else "Há 7 unidades.",
        assumptions=[SQL] if field == "assumptions" else [],
    )
    decision = validate_output(
        synthesis.answer,
        synthesis.assumptions,
        "Mostre o SQL executado.",
        SQL,
        _result(),
    )
    assert decision.decision == OutputGuardrailDecision.BLOCK
    assert decision.reason == OutputGuardrailReason.SQL_IN_ANSWER


@pytest.mark.parametrize("field", ["answer", "assumptions"])
@pytest.mark.parametrize("unsupported", ["Há 999 unidades.", "Período: 2024-01."])
def test_question_numbers_and_dates_are_not_evidence(field, unsupported):
    prompt = load_synthesis_prompts()
    assert "Fundamente `answer` e `assumptions` apenas no resultado e no SQL" in prompt
    assert "Números escritos na pergunta do usuário não são evidência" in prompt
    assert "datas que aparecem no SQL executado ou no resultado" in prompt

    decision = validate_output(
        unsupported if field == "answer" else "Há 7 unidades.",
        [unsupported] if field == "assumptions" else [],
        "Confirme 999 unidades em 2024-01.",
        SQL,
        _result(),
    )
    assert decision.decision == OutputGuardrailDecision.BLOCK
    assert decision.reason == OutputGuardrailReason.UNSUPPORTED_NUMBER


def test_sql_date_can_ground_an_assumption_without_exposing_sql():
    prompt = load_synthesis_prompts()
    assert "sustentados pelo SQL ou resultado" in prompt
    decision = validate_output(
        "Há 7 unidades.",
        ["Período: 2026-06-01."],
        "Quantas unidades?",
        SQL + " WHERE data = '2026-06-01'",
        _result(),
    )
    assert decision.decision == OutputGuardrailDecision.ALLOW


@pytest.mark.parametrize("truncated", [False, True])
def test_simple_sum_is_allowed_only_for_complete_results(truncated):
    prompt = load_synthesis_prompts()
    assert "somente quando o resultado estiver completo" in prompt
    assert "Respeite as fontes e os cálculos permitidos" in prompt
    assert "invente valores que não estejam no resultado" not in prompt

    decision = validate_output(
        "A soma das quantidades retornadas é 5.",
        [],
        "Qual a soma?",
        SQL,
        _result(rows=[[2], [3]], truncated=truncated),
    )
    if truncated:
        assert decision.decision == OutputGuardrailDecision.BLOCK
        assert decision.reason == OutputGuardrailReason.UNSUPPORTED_NUMBER
    else:
        assert decision.decision == OutputGuardrailDecision.ALLOW


def test_month_display_and_metric_instructions_preserve_source_meaning():
    from app.agent.prompts.sql_generation.loader import load_sql_generation_prompts
    from app.agent.sql_generator import build_sql_generation_prompt
    synthesis = load_synthesis_prompts()
    sql_instructions = load_sql_generation_prompts()
    assert "janeiro de 2024" in synthesis
    assert "sem descartar o dia" in synthesis
    assert "não renomeie receita como gasto" in synthesis
    assert "NEEDS_CLARIFICATION" in sql_instructions
    assert 'Não trate "gastos" ou "despesas" como sinônimos automáticos de receita' in sql_instructions
    assert "subconjunto original" in sql_instructions
    prompt = build_sql_generation_prompt("Qual o menor dentre esses meses?", "Contrato sintético.", "Gasto definido pelo usuário como valor faturado; meses já selecionados.")
    assert "valor faturado" in prompt and "meses já selecionados" in prompt
