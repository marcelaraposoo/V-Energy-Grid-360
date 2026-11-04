import asyncio
import sqlite3
from dataclasses import replace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.agent.conversation import resolve_followup
from app.agent.state.memory_context import build_memory_context
from app.agent.schemas import MemoryEntry,AgentOutcome,SQLGenerationResult,SQLGenerationStatus,SynthesisResult,SynthesisStatus,QueryExecutionResult,OutputGuardrailDecision
from app.agent.intent_validation import sql_intent_problem

FIRST='Quantas UCs foram afetadas por interrupções no município de Caetés entre 2025-07 e 2026-06?'
FOLLOW='Na verdade, quero os bairros Caetés I, II e III em Abreu e Lima, no mesmo período.'
GOOD="SELECT COUNT(DISTINCT id_uc) AS ucs_afetadas FROM fato_interrupcao WHERE municipio='Abreu e Lima' AND bairro IN ('Caetés I','Caetés II','Caetés III') AND mes_referencia BETWEEN '2025-07' AND '2026-06'"
BAD="SELECT id_uc,mes_referencia,consumo_kwh,valor_total FROM fato_consumo_faturamento"


@pytest.mark.parametrize('follow', [FOLLOW,'Considere os bairros Caetés I, II e III em Abreu e Lima, mantendo o período.','Mude para os bairros Caetés I, II e III em Abreu e Lima.'])
def test_correction_preserves_aggregate_metric_and_period(follow):
    context=build_memory_context([MemoryEntry(question=FIRST,answer='Localidade não coberta.',outcome=AgentOutcome.NEEDS_CLARIFICATION)])
    resolved=resolve_followup(follow,context)
    assert 'Quantas UCs foram afetadas por interrupções' in resolved
    assert 'entre 2025-07 e 2026-06' in resolved
    assert 'Abreu e Lima' in resolved and 'município de Caetés' not in resolved


@pytest.mark.parametrize('sql', [BAD,'SELECT COUNT(*) FROM fato_interrupcao','SELECT COUNT(id_uc) FROM fato_interrupcao','SELECT COUNT(DISTINCT id_uc) FROM fato_consumo_faturamento','SELECT COUNT(DISTINCT id_uc) FROM fato_interrupcao GROUP BY id_uc'])
def test_detailed_or_repeated_uc_is_not_affected_count(sql):
    assert sql_intent_problem(FIRST,sql)
    from app.agent.guardrails.output_guardrail import validate_output
    decision=validate_output(answer='Foram 2 UCs.',assumptions=[],question=FIRST,sql=sql,result=QueryExecutionResult(columns=['total'],rows=[[2]],row_count=1))
    assert decision.decision==OutputGuardrailDecision.BLOCK


def test_distinct_interruption_query_is_eligible():
    assert sql_intent_problem(FIRST,GOOD) is None


@pytest.mark.parametrize('bad_provider',[False,True])
def test_full_http_locality_correction(monkeypatch,tmp_path,bad_provider):
    from app.agent import pipeline,sql_generator,answer_synthesizer,sql_executor,geography
    from app.agent.state.dependencies import AgentStateDependencies
    from app.agent.state.sqlite_audit import SQLiteAuditStore
    from app.routers import ia
    gold=tmp_path/'gold.db';portal=tmp_path/'portal.db'
    with sqlite3.connect(gold) as c:
        c.executescript('CREATE TABLE dim_uc(id_uc TEXT,municipio TEXT,bairro TEXT); CREATE TABLE fato_interrupcao(id_uc TEXT,municipio TEXT,bairro TEXT,mes_referencia TEXT);')
        c.executemany('INSERT INTO dim_uc VALUES (?,?,?)',[('u1','Abreu e Lima','Caetés I'),('u2','Abreu e Lima','Caetés II'),('u3','Abreu e Lima','Caetés III')])
        c.executemany('INSERT INTO fato_interrupcao VALUES (?,?,?,?)',[('u1','Abreu e Lima','Caetés I','2025-07'),('u1','Abreu e Lima','Caetés I','2025-08'),('u2','Abreu e Lima','Caetés II','2026-06')])
    class Memory:
        def __init__(self):self.turns={}
        async def get_context(self,key):return list(self.turns.get(key,[]))
        async def append(self,key,value):self.turns.setdefault(key,[]).append(value)
    memory=Memory();calls=[]
    async def generate(prompt,**kwargs):
        question=prompt.split('<user_question>\n')[1].split('\n</user_question>')[0]
        calls.append(question)
        assert 'Quantas UCs foram afetadas por interrupções' in question
        assert '2025-07' in question and '2026-06' in question and 'Abreu e Lima' in question
        return SQLGenerationResult(status=SQLGenerationStatus.READY,sql=BAD if bad_provider else GOOD),[],None
    async def synthesize(*args,**kwargs):return SynthesisResult(status=SynthesisStatus.ANSWERED,answer='Foram 2 UCs.'),[],None
    monkeypatch.setattr(sql_generator,'run_with_fallback',generate)
    monkeypatch.setattr(answer_synthesizer,'run_with_fallback',synthesize)
    monkeypatch.setattr(sql_executor,'settings',replace(sql_executor.settings,sqlite_path=str(gold)))
    monkeypatch.setattr(geography,'settings',replace(geography.settings,sqlite_path=str(gold)))
    monkeypatch.setattr(pipeline,'get_state_dependencies',lambda:AgentStateDependencies(memory_store=memory,audit_store=SQLiteAuditStore(str(portal))))
    app=FastAPI();app.include_router(ia.router);client=TestClient(app)
    first=client.post('/api/ia/perguntar',json={'pergunta':FIRST,'sessao_id':'isolated'})
    assert first.status_code==200 and first.json()['status']=='nao_sei' and not calls
    second=client.post('/api/ia/perguntar',json={'pergunta':FOLLOW,'sessao_id':'isolated'})
    assert second.status_code==200 and second.json()['status']==('nao_sei' if bad_provider else 'ok')
    with sqlite3.connect(portal) as c:
        rows=c.execute('SELECT outcome,cache_hit,row_count,truncated FROM agent_audit ORDER BY rowid').fetchall()
    assert rows[0][0]=='needs_clarification' and rows[0][2] is None
    assert rows[1][0]==('needs_clarification' if bad_provider else 'answered')
    assert all(r[1]==0 for r in rows)
    if not bad_provider:assert rows[1][2:]==(1,0)
