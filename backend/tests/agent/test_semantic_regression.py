"""Regressões com provedores simulados; integrações Gold explicitamente separadas."""
import asyncio
import json
import sqlite3
import time
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.agent.context import runtime
from app.agent.schemas import SQLGenerationResult, QueryExecutionResult


@pytest.fixture
def gold(tmp_path):
    path = tmp_path / 'gold.db'
    with sqlite3.connect(path) as con:
        con.executescript("""
            CREATE TABLE dim_uc(municipio TEXT,bairro TEXT);
            INSERT INTO dim_uc VALUES ('Recife','Macaxeira'),('Recife','Centro'),('Olinda','Centro');
            CREATE TABLE kpis_mensal(mes_referencia TEXT);
            INSERT INTO kpis_mensal VALUES ('2022-07'),('2026-06');
            CREATE TABLE fato_segmento_mensal(municipio TEXT,bairro TEXT,mes_referencia TEXT,consumo_kwh REAL);
            INSERT INTO fato_segmento_mensal VALUES ('Recife','Macaxeira','2026-06',120);
        """)
    return str(path)


def metadata(question, gold):
    return json.loads(runtime.build_runtime_context(question, gold).split('<metadados_consultados>')[1].split('</')[0])


def test_catalog_resolves_accent_variations_without_guessing(gold, monkeypatch):
    monkeypatch.setattr(runtime, 'reference_date', lambda: date(2026,11,8))
    data = metadata('Qual o consumo de macaxeira mês passado?', gold)
    assert data['bairros_mencionados'] == [{'municipio':'Recife', 'bairro':'Macaxeira'}]
    assert data['data_atual'] == '2026-11-08'
    assert data['municipios_cobertos'] == ['Olinda', 'Recife']
    assert data['cobertura_competencias']['fim'] == '2026-06'
    assert len(metadata('Consumo do Centro?', gold)['bairros_mencionados']) == 2
    assert metadata('Consumo de Imaginação?', gold)['bairros_mencionados'] == []


def test_missing_catalog_does_not_create_database(tmp_path):
    path = tmp_path / 'missing.db'
    assert metadata('Consumo?', str(path))['catalogo_disponivel'] is False
    assert not path.exists()


def test_relative_month_rolls_year_without_reinterpreting_followup(monkeypatch):
    monkeypatch.setattr(runtime, 'reference_date', lambda: date(2026,1,8))
    assert runtime.requested_month('Consumo mês passado?') == '2025-12'
    assert runtime.requested_month('E no mês passado?') is None


def test_relative_month_retries_once_before_executing(gold, monkeypatch):
    from app.agent import sql_execution_orchestrator as flow
    monkeypatch.setattr(runtime, 'reference_date', lambda: date(2026,11,8))
    wrong = "SELECT SUM(consumo_kwh) FROM fato_segmento_mensal WHERE mes_referencia='2026-05'"
    right = wrong.replace('2026-05','2026-10')
    provider = AsyncMock(side_effect=[(SQLGenerationResult(status='ready',sql=s),[],None) for s in (wrong,right)])
    monkeypatch.setattr(flow, 'generate_sql', provider)
    result = asyncio.run(flow.generate_validate_and_execute('Consumo mês passado?', 'schema', database_path=gold))
    assert result.executed and result.sql == right and result.regenerations == 1
    assert result.execution_result.rows == [[None]]
    assert '2026-10' in provider.await_args.kwargs['guardrail_feedback']


def test_wrong_relative_month_cannot_be_delivered_or_cached(gold, monkeypatch):
    from app.agent import sql_execution_orchestrator as flow
    monkeypatch.setattr(runtime, 'reference_date', lambda: date(2026,11,8))
    wrong = "SELECT SUM(consumo_kwh) FROM fato_segmento_mensal WHERE mes_referencia='2026-05'"
    monkeypatch.setattr(flow,'generate_sql',AsyncMock(return_value=(SQLGenerationResult(status='ready',sql=wrong),[],None)))
    lookup = AsyncMock()
    result = asyncio.run(flow.generate_validate_and_execute('Consumo mês passado?', 'schema', database_path=gold,cache_lookup=lookup))
    assert not result.executed and result.generation_status.value == 'insufficient_context'
    assert result.regenerations == 1
    lookup.assert_not_awaited()


def test_null_aggregate_is_no_data_without_provider(monkeypatch):
    from app.agent import answer_synthesizer as synthesis
    provider = AsyncMock(side_effect=AssertionError('Sem chamada para resultado ausente'))
    monkeypatch.setattr(synthesis,'run_with_fallback',provider)
    result, attempts, error = asyncio.run(synthesis.synthesize_answer('Consumo?', 'SELECT SUM(consumo_kwh) FROM fato_segmento_mensal',
        QueryExecutionResult(columns=['consumo','inicio','fim'], rows=[[None,None,None]],row_count=1)))
    assert result.status.value == 'no_data' and error is None and not attempts
    provider.assert_not_awaited()


@pytest.mark.parametrize('value,empty',[(None,True),(0,False),(120,False)])
def test_period_label_does_not_hide_null_measure(value,empty):
    from app.agent.result_semantics import has_no_data
    result = QueryExecutionResult(columns=['consumo','mes'],rows=[[value,'2026-10']],row_count=1)
    assert has_no_data("SELECT SUM(consumo_kwh), '2026-10' FROM fato_segmento_mensal",result) is empty


def test_domain_refusal_is_reconsidered_without_authorizing_writes(monkeypatch,gold):
    from app.agent import sql_execution_orchestrator as flow
    provider = AsyncMock(side_effect=[
        (SQLGenerationResult(status='out_of_scope',reason='Local desconhecido'),[],None),
        (SQLGenerationResult(status='ready',sql="DELETE FROM dim_uc"),[],None),
    ])
    monkeypatch.setattr(flow,'generate_sql',provider)
    result = asyncio.run(flow.generate_validate_and_execute('Qual o consumo de Cidade Inexistente?', 'schema',database_path=gold))
    assert not result.executed and result.guardrail_reason is not None and result.regenerations == 1
    with sqlite3.connect(gold) as con:
        assert con.execute('SELECT COUNT(*) FROM dim_uc').fetchone()[0] == 3


def test_repeated_scope_refusal_asks_for_clarification(monkeypatch,gold):
    from app.agent import sql_execution_orchestrator as flow
    provider=AsyncMock(return_value=(SQLGenerationResult(status='out_of_scope',reason='Local desconhecido'),[],None))
    monkeypatch.setattr(flow,'generate_sql',provider)
    result=asyncio.run(flow.generate_validate_and_execute('Qual o consumo de Cidade Inexistente?', 'schema',database_path=gold))
    assert result.generation_status.value == 'needs_clarification' and not result.executed
    assert provider.await_count == 2


@pytest.mark.parametrize('question',['E no ano passado?','E em Caruaru?','Agora compara os dois.','E no mês anterior?'])
def test_followups_reach_semantic_provider_with_history(monkeypatch,question):
    from app.agent import sql_generator
    history = 'Usuário: Consumo de Recife em 2026?\nAssistente: 120 kWh em janeiro de 2026.'
    provider = AsyncMock(return_value=(SQLGenerationResult(status='needs_clarification',reason='Qual comparação deseja?'),[],None))
    monkeypatch.setattr(sql_generator,'run_with_fallback',provider)
    asyncio.run(sql_generator.generate_sql(question,'schema',history))
    provider.assert_awaited_once()
    assert history in provider.await_args.args[0]


def test_calendar_change_invalidates_cache(monkeypatch):
    from app.agent.state.cache_key import build_cache_key
    kwargs = dict(normalized_question='Consumo mês passado?',session_id='one',data_version='gold-v1')
    monkeypatch.setattr(runtime,'reference_date',lambda:date(2026,10,31))
    first = build_cache_key(**kwargs)
    monkeypatch.setattr(runtime,'reference_date',lambda:date(2026,11,1))
    assert first != build_cache_key(**kwargs)


def test_period_in_output_literal_does_not_override_wrong_filter(monkeypatch):
    monkeypatch.setattr(runtime,'reference_date',lambda:date(2026,11,8))
    sql = "SELECT '2026-10',SUM(consumo_kwh) FROM fato_segmento_mensal WHERE mes_referencia='2026-05'"
    assert runtime.relative_period_problem('Consumo mês passado?',sql)


def test_complete_question_starting_with_e_em_is_allowed():
    from app.agent.context_requirement import requires_complete_question
    assert not requires_complete_question('E em Recife qual foi o consumo em 2026?')


def test_annual_followup_preserves_original_request_not_partial_answer():
    memory='Usuário: Qual o consumo de Recife em 2026 total?\nAssistente: Dados de janeiro a junho de 2026.'
    assert runtime.followup_year('E no ano passado?',memory) == '2025'
    wrong="SELECT SUM(consumo_kwh) FROM fato_segmento_mensal WHERE mes_referencia BETWEEN '2025-01' AND '2025-06'"
    assert runtime.followup_period_problem('E no ano passado?',memory,wrong)
    assert runtime.followup_period_problem('E no ano passado?',memory,wrong.replace('2025-06','2025-12')) is None
    assert runtime.followup_year('E no ano passado?',memory.replace('em 2026 total','em junho de 2026')) is None


def test_sql_does_not_block_event_loop(gold,monkeypatch):
    from app.agent import sql_execution_orchestrator as flow
    from app.agent.sql_executor import execute_sql
    sql = 'SELECT SUM(consumo_kwh) FROM fato_segmento_mensal'
    monkeypatch.setattr(flow,'generate_sql',AsyncMock(return_value=(SQLGenerationResult(status='ready',sql=sql),[],None)))
    def slow(*args, **kwargs):
        time.sleep(.08)
        return execute_sql(*args,**kwargs)
    monkeypatch.setattr(flow,'execute_sql',slow)
    async def run():
        task = asyncio.create_task(flow.generate_validate_and_execute('Consumo?', 'schema', database_path=gold))
        await asyncio.sleep(.02)
        assert not task.done(), 'A consulta bloqueou o event loop até terminar'
        return await task
    assert asyncio.run(run()).executed


def test_real_gold_aggregate_and_catalog_are_read_only():
    from app.agent.sql_executor import execute_sql
    from app.agent.guardrails.sql_guardrail import validate_sql
    path = Path(__file__).resolve().parents[3] / 'data/gold/gold.db'
    if not path.exists():
        pytest.skip('Gold real ausente')
    before = path.stat()
    sql = "SELECT SUM(consumo_kwh), MIN(mes_referencia),MAX(mes_referencia) FROM fato_segmento_mensal WHERE municipio='Recife' AND mes_referencia BETWEEN '2026-01' AND '2026-12'"
    assert validate_sql(sql).decision.value == 'allow'
    result = execute_sql(sql,database_path=str(path))
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as con:
        expected = con.execute(sql).fetchall()
    assert result.result.rows == [list(r) for r in expected]
    assert metadata('Macaxeira',str(path))['bairros_mencionados'] == [{'municipio':'Recife','bairro':'Macaxeira'}]
    assert (before.st_size,before.st_mtime_ns) == (path.stat().st_size,path.stat().st_mtime_ns)
