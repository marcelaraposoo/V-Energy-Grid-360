import pytest

from app.agent.guardrails.sql_guardrail import validate_sql
from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM consumo_energia;",
        "-- consulta segura\nSELECT * FROM consumo_energia",
        (
            "SELECT * "
            "FROM consumo_energia "
            "/* comentário interno */"
        ),
        (
            "SELECT municipio FROM consumo_energia "
            "UNION "
            "SELECT municipio FROM faturamento"
        ),
        (
            "SELECT municipio FROM consumo_energia "
            "INTERSECT "
            "SELECT municipio FROM faturamento"
        ),
        (
            "SELECT municipio FROM consumo_energia "
            "EXCEPT "
            "SELECT municipio FROM faturamento"
        ),
    ],
)
def test_allows_safe_read_only_variations(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None
    assert result.retryable is False


@pytest.mark.parametrize(
    "sql",
    [
        (
            "SELECT * FROM consumo_energia; "
            "DROP TABLE consumo_energia"
        ),
        (
            "SELECT * FROM consumo_energia; "
            "UPDATE faturamento SET valor_fatura = 0"
        ),
        (
            "SELECT * FROM consumo_energia; "
            "INSERT INTO faturamento "
            "(id_faturamento) VALUES (1)"
        ),
        (
            "SELECT * FROM consumo_energia; "
            "DELETE FROM faturamento"
        ),
    ],
)
def test_blocks_read_query_followed_by_write_operation(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.MULTIPLE_STATEMENTS
    )
    assert result.retryable is True


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA table_info(consumo_energia)",
        "VACUUM",
        "ATTACH DATABASE 'outro.db' AS outro",
        "DETACH DATABASE outro",
        "BEGIN TRANSACTION",
        "COMMIT",
        "ROLLBACK",
    ],
)
def test_blocks_non_read_only_or_administrative_commands(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK

    assert result.reason in {
        SQLGuardrailReason.INVALID_SQL,
        SQLGuardrailReason.FORBIDDEN_OPERATION,
    }

    assert result.retryable is True


def test_dangerous_words_inside_string_do_not_trigger_block():
    sql = (
        "SELECT * FROM atendimentos "
        "WHERE tipo_atendimento = "
        "'DELETE FROM faturamento'"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_dangerous_words_inside_comment_do_not_trigger_block():
    sql = (
        "SELECT * FROM consumo_energia "
        "/* DROP TABLE faturamento */"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_semicolon_inside_string_is_not_multiple_statements():
    sql = (
        "SELECT * FROM atendimentos "
        "WHERE tipo_atendimento = 'falha; urgente'"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_multiple_safe_selects_are_still_blocked():
    sql = (
        "SELECT * FROM consumo_energia; "
        "SELECT * FROM faturamento"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.MULTIPLE_STATEMENTS
    )
    assert result.retryable is True