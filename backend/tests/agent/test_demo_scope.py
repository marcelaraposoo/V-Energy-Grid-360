import asyncio
from unittest.mock import AsyncMock

import pytest

from app.agent.context_requirement import requires_complete_question, COMPLETE_QUESTION_MESSAGE
from app.agent.intent_validation import sql_intent_problem
from app.agent.schemas import QueryExecutionResult


@pytest.mark.parametrize("question", [
    "E nos últimos 6 meses?", "Agora FEC", "Agora TOP 2", "E no município de Olinda?",
    "Mostre um gráfico disso", "E no mês anterior?", "Qual o consumo dessas UCs?",
])
def test_context_dependent_question_requires_complete_request(question):
    assert requires_complete_question(question)


@pytest.mark.parametrize("question", [
    "Quantas UCs existem?", "Qual o DEC?", "Quantas UCs em Olinda?",
    "Quais os 3 alimentadores com maior FEC em 2026-06?",
    "E quantas UCs existem em Recife?",
])
def test_short_but_complete_question_is_not_blocked(question):
    assert not requires_complete_question(question)


@pytest.mark.parametrize("history", [None, "Pergunta e resposta anteriores aprovadas."])
def test_context_guard_precedes_cache_and_provider_and_audits(monkeypatch, history):
    from app.agent import pipeline
    from app.agent.state.dependencies import AgentStateDependencies
    audit = AsyncMock()
    cache = AsyncMock()
    deps = AgentStateDependencies(audit_store=audit, cache_store=cache, data_version="demo-test")
    state = AsyncMock(side_effect=AssertionError("Não buscar cache de pedido incompleto"))
    sql = AsyncMock(side_effect=AssertionError("Não chamar provider"))
    monkeypatch.setattr(pipeline, "prepare_request_state", state)
    monkeypatch.setattr(pipeline, "generate_validate_and_execute", sql)
    result = asyncio.run(pipeline.answer_question("E nos últimos 6 meses?", session_id="s", state_dependencies=deps, memory_context=history))
    assert result.message == COMPLETE_QUESTION_MESSAGE
    assert result.outcome.value == "needs_clarification" and not result.cache_hit
    state.assert_not_awaited()
    sql.assert_not_awaited()
    cache.set.assert_not_awaited()
    audit.save.assert_awaited_once()


def test_isolated_generator_also_requires_complete_question(monkeypatch):
    from app.agent import sql_generator
    provider = AsyncMock(side_effect=AssertionError("Não chamar provider"))
    monkeypatch.setattr(sql_generator, "run_with_fallback", provider)
    out, attempts, error = asyncio.run(sql_generator.generate_sql("Agora FEC", "schema", memory_context="Histórico anterior"))
    assert out.status.value == "needs_clarification" and out.reason == COMPLETE_QUESTION_MESSAGE
    assert attempts == [] and error is None
    provider.assert_not_awaited()


@pytest.mark.parametrize("question,sql,blocked", [
    ("TOP 15 alimentadores", "SELECT alimentador FROM dec_fec_alimentador_mensal LIMIT 10", True),
    ("TOP 15 alimentadores", "SELECT alimentador FROM dec_fec_alimentador_mensal LIMIT 15", False),
    ("Qual o valor faturado?", "SELECT receita_energia FROM kpis_mensal", True),
    ("Qual o valor faturado?", "SELECT receita_total FROM kpis_mensal", False),
    ("Qual a receita de energia sem tributos?", "SELECT receita_total FROM kpis_mensal", True),
    ("Qual a receita de energia sem tributos?", "SELECT receita_energia FROM kpis_mensal", False),
    ("Qual o DEC nos últimos 6 meses?", "SELECT dec_12m_horas FROM dec_fec_alimentador_mensal", True),
    ("Qual o DEC nos últimos 12 meses?", "SELECT dec_12m_horas FROM dec_fec_alimentador_mensal", False),
    ("Quais alimentadores tiveram pior DEC nos últimos 12 meses?", "SELECT dec_12m_horas FROM dec_fec_alimentador_mensal LIMIT 10", False),
    ("Quantas UCs sofreram interrupções?", "SELECT COUNT(*) FROM fato_interrupcao", True),
    ("Quantas UCs sofreram interrupções?", "SELECT COUNT(DISTINCT id_uc) FROM fato_consumo_faturamento", True),
    ("Quantas UCs sofreram interrupções?", "SELECT COUNT(DISTINCT id_uc) FROM fato_interrupcao", False),
])
def test_sql_intent_checks_remain(question, sql, blocked):
    assert bool(sql_intent_problem(question, sql)) == blocked


def test_validated_sql_still_passes_c42_and_read_only_executor(tmp_path):
    import sqlite3
    from app.agent.guardrails.sql_guardrail import validate_sql
    from app.agent.sql_executor import execute_sql
    path = tmp_path / "gold.db"
    with sqlite3.connect(path) as c:
        c.executescript("CREATE TABLE fato_interrupcao(id_uc TEXT); INSERT INTO fato_interrupcao VALUES ('a'),('a'),('b');")
    sql = "SELECT COUNT(DISTINCT id_uc) AS ucs FROM fato_interrupcao"
    assert validate_sql(sql).decision.value == "allow"
    result = execute_sql(sql, database_path=str(path))
    assert result.result.rows == [[2]]
    assert execute_sql("DELETE FROM fato_interrupcao", database_path=str(path)).error_type is not None


def test_c5_preserves_numeric_security_and_sql_compatibility():
    from app.agent.guardrails.output_guardrail import validate_output
    result = QueryExecutionResult(columns=["receita_energia"], rows=[[100]], row_count=1)
    assert validate_output("R$ 100.", [], "Qual o valor faturado?", "SELECT receita_energia FROM kpis_mensal", result).decision.value == "block"
    assert validate_output("R$ 999.", [], "Qual a receita de energia?", "SELECT receita_energia FROM kpis_mensal", result).decision.value == "block"
