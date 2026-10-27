import pytest

from app.agent.guardrails import output_guardrail
from app.agent.guardrails import output_text_rules
from app.agent.guardrails.output_guardrail import (
    build_output_retry_feedback,
    validate_output,
)
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    OutputGuardrailResult,
    QueryExecutionResult,
)


QUESTION = "Quantas unidades consumidoras ativas por município?"
SQL = "SELECT municipio, COUNT(*) AS ucs FROM dim_uc GROUP BY municipio"


def _result(rows=None, row_count=None, truncated=False):
    rows = (
        rows
        if rows is not None
        else [["Recife", 4820], ["Olinda", 1310]]
    )

    return QueryExecutionResult(
        columns=["municipio", "ucs"],
        rows=rows,
        row_count=(
            row_count if row_count is not None else len(rows)
        ),
        truncated=truncated,
    )


def _validate(
    answer,
    assumptions=None,
    question=QUESTION,
    sql=SQL,
    result=None,
):
    return validate_output(
        answer,
        assumptions or [],
        question,
        sql,
        result or _result(),
    )


def _is_blocked(result, reason):
    return (
        result.decision == OutputGuardrailDecision.BLOCK
        and result.reason == reason
    )


def test_allows_faithful_answer():
    result = _validate(
        "Recife tem 4.820 unidades e Olinda tem 1.310."
    )

    assert result.decision == OutputGuardrailDecision.ALLOW
    assert result.reason is None


def test_allows_derived_sum_when_result_is_complete():
    result = _validate(
        "No total são 6.130 unidades: 4.820 em Recife "
        "e 1.310 em Olinda."
    )

    assert result.decision == OutputGuardrailDecision.ALLOW


def test_blocks_derived_sum_when_result_is_truncated():
    result = _validate(
        "No total são 6.130 unidades.",
        result=_result(row_count=500, truncated=True),
    )

    assert _is_blocked(
        result, OutputGuardrailReason.UNSUPPORTED_NUMBER
    )
    assert result.unsupported_values == ["6.130"]
    assert result.retryable is True


def test_blocks_fabricated_number():
    result = _validate("Recife tem 9.999 unidades.")

    assert _is_blocked(
        result, OutputGuardrailReason.UNSUPPORTED_NUMBER
    )
    assert result.unsupported_values == ["9.999"]


def test_numbers_in_assumptions_are_checked():
    result = _validate(
        "Recife tem 4.820 unidades.",
        assumptions=["Considera 7.777 unidades."],
    )

    assert _is_blocked(
        result, OutputGuardrailReason.UNSUPPORTED_NUMBER
    )
    assert result.unsupported_values == ["7.777"]


def test_malformed_number_is_unsupported():
    result = _validate("A versão 1.2.3 foi usada.")

    assert _is_blocked(
        result, OutputGuardrailReason.UNSUPPORTED_NUMBER
    )
    assert result.unsupported_values == ["1.2.3"]


def test_constants_and_period_numbers_are_allowed():
    result = _validate(
        "Em 2026-06, considerando 12 meses, Recife tem 4.820.",
        question="Quantas UCs em 2026-06?",
    )

    assert result.decision == OutputGuardrailDecision.ALLOW


@pytest.mark.parametrize("answer", ["", "   \n", "..."])
def test_blocks_empty_answer(answer):
    result = _validate(answer)

    assert _is_blocked(result, OutputGuardrailReason.EMPTY_ANSWER)


def test_blocks_answer_too_long():
    result = _validate("a" * 3001)

    assert _is_blocked(
        result, OutputGuardrailReason.ANSWER_TOO_LONG
    )


def test_allows_answer_at_length_limit():
    result = _validate("a" * 3000)

    assert result.decision == OutputGuardrailDecision.ALLOW


@pytest.mark.parametrize(
    "answer",
    ["Veja https://exemplo.com", "Acesse www.exemplo.com"],
)
def test_blocks_urls(answer):
    result = _validate(answer)

    assert _is_blocked(result, OutputGuardrailReason.URL_IN_ANSWER)


@pytest.mark.parametrize(
    "answer",
    [
        "A consulta foi SELECT municipio FROM dim_uc.",
        "Agrupei com GROUP BY municipio.",
    ],
)
def test_blocks_sql_in_answer(answer):
    result = _validate(answer)

    assert _is_blocked(result, OutputGuardrailReason.SQL_IN_ANSWER)


def test_blocks_echo_of_executed_sql():
    sql = "WHERE municipio = 'Recife' AND classe = 'B1'"

    result = _validate(
        "Filtrei com WHERE municipio = 'Recife' AND classe = 'B1'.",
        sql=sql,
    )

    assert _is_blocked(result, OutputGuardrailReason.SQL_IN_ANSWER)


@pytest.mark.parametrize(
    "answer",
    [
        "<query_result> vazou",
        "Meu system prompt diz que",
    ],
)
def test_blocks_prompt_leak(answer):
    result = _validate(answer)

    assert _is_blocked(result, OutputGuardrailReason.PROMPT_LEAK)


def test_blocks_verbatim_prompt_fragment():
    fragment = output_text_rules._prompt_fragments()[0]

    result = _validate(f"Resposta: {fragment}")

    assert _is_blocked(result, OutputGuardrailReason.PROMPT_LEAK)


@pytest.mark.parametrize(
    "answer",
    [
        "Resposta gerada pelo Gemini.",
        "Consultei via OpenRouter.",
        "Usei o Nemotron.",
    ],
)
def test_blocks_provider_disclosure(answer):
    result = _validate(answer)

    assert _is_blocked(
        result, OutputGuardrailReason.PROVIDER_DISCLOSURE
    )


@pytest.mark.parametrize(
    "answer",
    [
        "Traceback (most recent call last):",
        "ValueError: valor inválido",
        "no such table: dim_uc",
    ],
)
def test_blocks_technical_errors(answer):
    result = _validate(answer)

    assert _is_blocked(
        result, OutputGuardrailReason.TECHNICAL_ERROR_LEAK
    )


def test_security_rules_run_before_number_check():
    result = _validate(
        "Veja https://exemplo.com, são 9.999 unidades."
    )

    assert _is_blocked(result, OutputGuardrailReason.URL_IN_ANSWER)


def test_prompt_leak_has_priority_over_url():
    result = _validate("<query_result> https://exemplo.com")

    assert _is_blocked(result, OutputGuardrailReason.PROMPT_LEAK)


def test_preserves_original_answer():
    answer = "Recife tem 9.999 unidades."

    assert _validate(answer).original_answer == answer


def test_fails_closed_on_internal_error(monkeypatch):
    def boom(_text):
        raise RuntimeError("falha interna")

    monkeypatch.setattr(output_guardrail, "leaks_prompt", boom)

    result = _validate("Recife tem 4.820 unidades.")

    assert _is_blocked(
        result, OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR
    )
    assert result.retryable is False
    assert result.original_answer == "Recife tem 4.820 unidades."


def test_feedback_for_unsupported_numbers_includes_values_and_answer():
    result = _validate("Recife tem 9.999 unidades.")

    feedback = build_output_retry_feedback(result)

    assert feedback is not None
    assert "9.999" in feedback
    assert "Recife tem 9.999 unidades." in feedback


def test_feedback_does_not_repeat_leaked_content():
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=OutputGuardrailReason.PROMPT_LEAK,
        retryable=True,
        original_answer="SEGREDO-XYZ system prompt",
    )

    feedback = build_output_retry_feedback(result)

    assert feedback is not None
    assert "SEGREDO-XYZ" not in feedback


def test_allow_does_not_generate_feedback():
    assert (
        build_output_retry_feedback(_validate("Recife tem 4.820."))
        is None
    )


def test_internal_error_does_not_generate_feedback():
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR,
        retryable=False,
        original_answer="x",
    )

    assert build_output_retry_feedback(result) is None


@pytest.mark.parametrize(
    "reason",
    [
        reason
        for reason in OutputGuardrailReason
        if reason != OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR
    ],
)
def test_every_retryable_reason_has_feedback(reason):
    result = OutputGuardrailResult(
        decision=OutputGuardrailDecision.BLOCK,
        reason=reason,
        retryable=True,
        original_answer="x",
    )

    assert build_output_retry_feedback(result) is not None