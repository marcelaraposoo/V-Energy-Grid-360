import asyncio
import sqlite3
from unittest.mock import AsyncMock
import pytest
from app.agent.conversation import resolve_followup
from app.agent.geography import geographic_clarification
from app.agent.intent_validation import sql_intent_problem
from app.agent.schemas import AgentOutcome, MemoryEntry, QueryExecutionResult, OutputGuardrailDecision
from app.agent.state.memory_context import build_memory_context


@pytest.fixture
def geography(tmp_path):
    p=tmp_path/'gold.db'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE dim_uc(municipio TEXT,bairro TEXT)')
        c.executemany('INSERT INTO dim_uc VALUES (?,?)',[('Abreu e Lima','Caetés '+v) for v in ['I','II','III']])
    return str(p)


@pytest.mark.parametrize('question',[
 'Liste 15 alimentadores por DEC em ordem decrescente.',
 'Quais 15 alimentadores em geral tiveram pior DEC?',
 'Quais municípios em todo o histórico tiveram maior consumo?',
])
def test_non_geographic_preposition_is_not_location(question,geography):
    assert geographic_clarification(question,geography) is None


def test_unknown_explicit_municipality_still_requires_confirmation(geography):
    assert geographic_clarification('Quantas UCs em município de Desconhecido?',geography)


def test_geographic_deltas_preserve_interruption_metric_and_period_after_failure():
    first='Quantas UCs afetadas por interrupções no município de Caetés entre 2025-07 e 2026-06?'
    correction='Nos bairros Caetés I, II e III em Abreu e Lima.'
    turns=[MemoryEntry(question='Qual consumo em novembro de 2025?',answer='Outro assunto.',outcome=AgentOutcome.ANSWERED),MemoryEntry(question=first,answer='Sem cobertura.',outcome=AgentOutcome.INSUFFICIENT_CONTEXT)]
    resolved=resolve_followup(correction,build_memory_context(turns))
    assert 'interrupções' in resolved and '2025-07' in resolved and 'Abreu e Lima' in resolved
    assert 'consumo' not in resolved
    turns.append(MemoryEntry(question=correction,answer='Resposta incompatível antiga.',outcome=AgentOutcome.ANSWERED))
    narrowed=resolve_followup('E apenas no bairro Caetés III?',build_memory_context(turns))
    assert 'bairro Caetés III' in narrowed and 'interrupções' in narrowed and '2026-06' in narrowed
    assert 'bairros Caetés I,' not in narrowed and 'novembro' not in narrowed


@pytest.mark.parametrize('sql,blocked',[
 ('SELECT alimentador,dec_horas FROM dec_fec_alimentador_mensal ORDER BY dec_horas DESC LIMIT 15',False),
 ('SELECT alimentador,dec_horas FROM dec_fec_alimentador_mensal ORDER BY dec_horas DESC LIMIT 10',True),
])
def test_top_count_contract(sql,blocked):
    assert bool(sql_intent_problem('Ranking geral de 15 alimentadores por DEC',sql))==blocked


@pytest.mark.parametrize('question,column,blocked',[
 ('Qual o valor faturado?', 'receita_energia',True),
 ('Qual o valor faturado?', 'receita_total',False),
 ('Qual a receita de energia sem tributos?', 'receita_total',True),
 ('Qual a receita de energia sem tributos?', 'receita_energia',False),
])
def test_financial_metrics_are_not_interchangeable(question,column,blocked):
    assert bool(sql_intent_problem(question,f'SELECT {column} FROM kpis_mensal'))==blocked


def test_c5_rejects_supported_number_for_wrong_financial_metric():
    from app.agent.guardrails.output_guardrail import validate_output
    r=validate_output(answer='O valor faturado foi R$ 100.',assumptions=[],question='Qual o valor faturado?',sql='SELECT receita_energia FROM kpis_mensal',result=QueryExecutionResult(columns=['receita_energia'],rows=[[100]],row_count=1))
    assert r.decision==OutputGuardrailDecision.BLOCK


def test_operational_expenses_clarification_terminates_without_llm(monkeypatch):
    from app.agent import pipeline
    from app.agent.state.dependencies import AgentStateDependencies
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import ia
    class Memory:
        entries=[]
        async def get_context(self,key):return list(self.entries)
        async def append(self,key,value):self.entries.append(value)
    memory=Memory();audit=type('Audit',(),{'save':AsyncMock()})()
    monkeypatch.setattr(pipeline,'get_state_dependencies',lambda:AgentStateDependencies(memory_store=memory,audit_store=audit))
    async def forbidden(*a,**k):pytest.fail('Não executar SQL ou LLM para métrica ausente')
    monkeypatch.setattr(pipeline,'generate_validate_and_execute',forbidden)
    app=FastAPI();app.include_router(ia.router);client=TestClient(app)
    for question in ['Quais os 3 meses com maiores gastos?','Despesas operacionais, não faturamento.']:
        response=client.post('/api/ia/perguntar',json={'pergunta':question,'sessao_id':'synthetic-final'})
        assert response.status_code==200
    assert audit.save.await_args_list[0].args[0].outcome==AgentOutcome.NEEDS_CLARIFICATION
    assert audit.save.await_args_list[1].args[0].outcome==AgentOutcome.INSUFFICIENT_CONTEXT


def test_insufficient_turn_retains_only_question_not_unverified_answer():
    from app.agent.state.records import build_memory_entry
    turn=build_memory_entry(question='Quantas UCs afetadas por interrupções no município de Caetés entre 2025-07 e 2026-06?',answer='Conteúdo não comprovado.',outcome=AgentOutcome.INSUFFICIENT_CONTEXT)
    assert turn and turn.answer=='Intenção pendente; nenhuma resposta foi aprovada.'
    resolved=resolve_followup('Nos bairros Caetés I, II e III em Abreu e Lima.',build_memory_context([turn]))
    assert 'interrupções' in resolved and '2025-07' in resolved


def test_temporal_window_is_not_top_count():
    assert sql_intent_problem('Quais alimentadores tiveram pior DEC nos últimos 12 meses?', 'SELECT alimentador,dec_12m_horas FROM dec_fec_alimentador_mensal ORDER BY dec_12m_horas DESC LIMIT 10') is None
