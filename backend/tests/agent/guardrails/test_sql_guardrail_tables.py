import json
from pathlib import Path

import pytest

from app.agent.guardrails.allowed_tables import ALLOWED_TABLES
from app.agent.guardrails.sql_guardrail import (
    build_retry_feedback,
    validate_sql,
)
from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
)


def test_allowed_tables_match_gold_agent_contract():
    contract_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "gold_agent_contract.json"
    )
    contract_tables = set(
        json.loads(contract_path.read_text(encoding="utf-8"))["tables"]
    )

    assert ALLOWED_TABLES == contract_tables
    assert "fato_segmento_mensal" not in contract_tables


@pytest.mark.parametrize("table", sorted(ALLOWED_TABLES))
def test_every_allowed_table_passes(table):
    result = validate_sql(f"SELECT COUNT(*) FROM {table}")

    assert result.decision == SQLGuardrailDecision.ALLOW


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM sqlite_master",
        "SELECT * FROM sqlite_stat1",
        "SELECT * FROM fato_segmento_mensal",
        "SELECT * FROM tabela_inventada",
        "SELECT * FROM dim_uc JOIN outra_tabela ON 1 = 1",
        "SELECT * FROM dim_uc WHERE id_uc IN (SELECT id_uc FROM oculta)",
        "SELECT * FROM main.sqlite_master",
    ],
)
def test_unknown_tables_are_blocked(sql):
    result = validate_sql(sql)

    assert result.decision == SQLGuardrailDecision.BLOCK
    assert result.reason == SQLGuardrailReason.UNKNOWN_TABLE
    assert result.retryable is True


def test_cte_names_are_not_treated_as_tables():
    sql = (
        "WITH base AS (SELECT classe, COUNT(*) AS n FROM dim_uc "
        "GROUP BY classe) SELECT * FROM base"
    )

    assert validate_sql(sql).decision == SQLGuardrailDecision.ALLOW


def test_table_names_are_case_insensitive():
    assert (
        validate_sql("SELECT 1 FROM DIM_UC").decision
        == SQLGuardrailDecision.ALLOW
    )


def test_aliases_are_not_treated_as_tables():
    sql = (
        "SELECT u.classe FROM dim_uc AS u "
        "JOIN fila_inspecao f ON u.id_uc = f.id_uc"
    )

    assert validate_sql(sql).decision == SQLGuardrailDecision.ALLOW


def test_unknown_table_has_retry_feedback():
    result = validate_sql("SELECT * FROM tabela_inventada")

    feedback = build_retry_feedback(result)

    assert feedback is not None
    assert "tabela_inventada" in feedback
