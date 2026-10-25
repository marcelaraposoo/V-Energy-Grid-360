import pytest

from app.agent.guardrails.sql_guardrail import validate_sql
from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM consumo_energia",
        (
            "SELECT municipio, SUM(consumo_kwh) "
            "FROM consumo_energia "
            "GROUP BY municipio"
        ),
        (
            "SELECT c.municipio, f.valor_fatura "
            "FROM consumo_energia AS c "
            "JOIN faturamento AS f "
            "ON c.id_unidade = f.id_unidade"
        ),
        (
            "SELECT municipio, "
            "CASE "
            "WHEN consumo_kwh > 1000 THEN 'alto' "
            "ELSE 'baixo' "
            "END AS faixa_consumo "
            "FROM consumo_energia"
        ),
        (
            "SELECT municipio, AVG(consumo_kwh) "
            "FROM consumo_energia "
            "WHERE ano_referencia = 2026 "
            "GROUP BY municipio "
            "HAVING AVG(consumo_kwh) > 500 "
            "ORDER BY municipio "
            "LIMIT 10"
        ),
    ],
)
def test_allows_read_only_queries(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None
    assert result.retryable is False
    assert result.original_sql == sql


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO consumo_energia VALUES (1)",
        (
            "UPDATE consumo_energia "
            "SET consumo_kwh = 0"
        ),
        "DELETE FROM consumo_energia",
        "DROP TABLE consumo_energia",
        (
            "ALTER TABLE consumo_energia "
            "ADD COLUMN teste TEXT"
        ),
        "CREATE TABLE teste (id INTEGER)",
        "TRUNCATE TABLE consumo_energia",
    ],
)
def test_blocks_forbidden_operations(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.FORBIDDEN_OPERATION
    )
    assert result.retryable is True
    assert result.original_sql == sql


def test_blocks_multiple_statements():
    sql = (
        "SELECT * FROM consumo_energia; "
        "DELETE FROM consumo_energia;"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.MULTIPLE_STATEMENTS
    )
    assert result.retryable is True
    assert result.original_sql == sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "\n\t",
    ],
)
def test_blocks_empty_sql(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.INVALID_SQL
    )
    assert result.retryable is True
    assert result.original_sql == sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT FROM",
        "SELECT * FORM consumo_energia",
        "THIS IS NOT SQL",
    ],
)
def test_blocks_invalid_sql(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.INVALID_SQL
    )
    assert result.retryable is True
    assert result.original_sql == sql


def test_blocks_window_functions():
    sql = (
        "SELECT municipio, "
        "ROW_NUMBER() OVER ("
        "PARTITION BY municipio "
        "ORDER BY consumo_kwh DESC"
        ") AS posicao "
        "FROM consumo_energia"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.UNSUPPORTED_QUERY
    )
    assert result.retryable is True
    assert result.original_sql == sql


def test_blocks_select_with_embedded_delete():
    sql = (
        "SELECT * FROM consumo_energia; "
        "DELETE FROM faturamento"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.MULTIPLE_STATEMENTS
    )
    assert result.retryable is True


def test_preserves_original_sql():
    sql = (
        "  SELECT * "
        "FROM consumo_energia  "
    )

    result = validate_sql(sql)

    assert result.original_sql == sql


def test_internal_error_is_not_retryable(
    monkeypatch,
):
    def fake_parse(*args, **kwargs):
        raise RuntimeError(
            "falha interna simulada"
        )

    monkeypatch.setattr(
        "app.agent.guardrails.sql_guardrail.parse",
        fake_parse,
    )

    sql = "SELECT * FROM consumo_energia"

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.GUARDRAIL_INTERNAL_ERROR
    )
    assert result.retryable is False
    assert result.original_sql == sql