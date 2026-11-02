import pytest

from app.agent.guardrails.sql_guardrail import validate_sql
from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM fato_consumo_faturamento;",
        "-- consulta segura\nSELECT * FROM fato_consumo_faturamento",
        (
            "SELECT * "
            "FROM fato_consumo_faturamento "
            "/* comentário interno */"
        ),
        (
            "SELECT municipio FROM fato_consumo_faturamento "
            "UNION "
            "SELECT municipio FROM dim_uc"
        ),
        (
            "SELECT municipio FROM fato_consumo_faturamento "
            "INTERSECT "
            "SELECT municipio FROM dim_uc"
        ),
        (
            "SELECT municipio FROM fato_consumo_faturamento "
            "EXCEPT "
            "SELECT municipio FROM dim_uc"
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
            "SELECT * FROM fato_consumo_faturamento; "
            "DROP TABLE fato_consumo_faturamento"
        ),
        (
            "SELECT * FROM fato_consumo_faturamento; "
            "UPDATE kpis_mensal SET receita_total = 0"
        ),
        (
            "SELECT * FROM fato_consumo_faturamento; "
            "INSERT INTO kpis_mensal "
            "(mes_referencia) VALUES ('2026-06')"
        ),
        (
            "SELECT * FROM fato_consumo_faturamento; "
            "DELETE FROM kpis_mensal"
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
        "PRAGMA table_info(fato_consumo_faturamento)",
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
        "SELECT * FROM fato_atendimento "
        "WHERE assunto = "
        "'DELETE FROM fato_consumo_faturamento'"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_dangerous_words_inside_comment_do_not_trigger_block():
    sql = (
        "SELECT * FROM fato_consumo_faturamento "
        "/* DROP TABLE kpis_mensal */"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_semicolon_inside_string_is_not_multiple_statements():
    sql = (
        "SELECT * FROM fato_atendimento "
        "WHERE assunto = 'falha; urgente'"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.ALLOW
    assert result.reason is None


def test_multiple_safe_selects_are_still_blocked():
    sql = (
        "SELECT * FROM fato_consumo_faturamento; "
        "SELECT * FROM kpis_mensal"
    )

    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert (
        result.reason
        == SQLGuardrailReason.MULTIPLE_STATEMENTS
    )
    assert result.retryable is True
