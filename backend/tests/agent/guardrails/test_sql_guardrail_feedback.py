import pytest

from app.agent.guardrails.sql_guardrail import (
    build_retry_feedback,
    validate_sql,
)
from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
    SQLGuardrailResult,
)


@pytest.mark.parametrize(
    "sql, expected_reason",
    [
        (
            "THIS IS NOT SQL",
            SQLGuardrailReason.INVALID_SQL,
        ),
        (
            "SELECT * FROM fato_consumo_faturamento; "
            "SELECT * FROM kpis_mensal",
            SQLGuardrailReason.MULTIPLE_STATEMENTS,
        ),
        (
            "DELETE FROM fato_consumo_faturamento",
            SQLGuardrailReason.FORBIDDEN_OPERATION,
        ),
        (
            (
                "SELECT municipio, "
                "ROW_NUMBER() OVER ("
                "ORDER BY consumo_kwh"
                ") AS posicao "
                "FROM fato_consumo_faturamento"
            ),
            SQLGuardrailReason.UNSUPPORTED_QUERY,
        ),
    ],
)
def test_builds_retry_feedback(
    sql,
    expected_reason,
):
    result = validate_sql(sql)

    assert result.reason == expected_reason

    feedback = build_retry_feedback(result)

    assert feedback is not None
    assert sql in feedback
    assert "Motivo da rejeição" in feedback
    assert "Gere uma nova consulta" in feedback


def test_allow_does_not_generate_retry_feedback():
    result = validate_sql(
        "SELECT * FROM fato_consumo_faturamento"
    )

    assert (
        result.decision
        == SQLGuardrailDecision.ALLOW
    )

    assert build_retry_feedback(result) is None


def test_internal_error_does_not_generate_retry_feedback():
    result = SQLGuardrailResult(
        decision=SQLGuardrailDecision.BLOCK,
        reason=(
            SQLGuardrailReason.GUARDRAIL_INTERNAL_ERROR
        ),
        retryable=False,
        original_sql=(
            "SELECT * FROM fato_consumo_faturamento"
        ),
    )

    assert build_retry_feedback(result) is None
