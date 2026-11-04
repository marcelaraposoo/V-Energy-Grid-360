import asyncio
from dataclasses import replace
import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.agent.conversation import resolve_followup, financial_clarification
from app.agent.schemas import AgentOutcome, MemoryEntry, SQLGenerationResult,SQLGenerationStatus,SynthesisResult,SynthesisStatus
from app.agent.state.memory_context import build_memory_context
from app.agent.geography import geographic_clarification


def entry(q, status=AgentOutcome.ANSWERED):
    return MemoryEntry(question=q,answer='Resposta sintética.',outcome=status)


@pytest.mark.parametrize('metric', ['DEC','FEC'])
@pytest.mark.parametrize('months',[3,6,9])
def test_followup_changes_only_explicit_dimension(metric,months):
    original=f'Quais alimentadores tiveram pior {metric} nos últimos 12 meses em Recife?'
    context=build_memory_context([entry(original)])
    resolved=resolve_followup(f'E nos últimos {months} meses?',context)
    assert resolved==original.replace('12 meses',f'{months} meses')


def test_metric_change_keeps_pending_user_period_not_assistant_detour():
    entries=[entry('Quais alimentadores tiveram pior DEC nos últimos 12 meses?'),entry('E nos últimos 6 meses?',AgentOutcome.NEEDS_CLARIFICATION)]
    assert resolve_followup('Agora considere o FEC.',build_memory_context(entries))=='Quais alimentadores tiveram pior FEC nos últimos 6 meses?'


def test_unresolved_or_incompatible_followup_is_not_silently_dropped():
    assert resolve_followup('E nos últimos 6 meses?',build_memory_context([entry('Quantas UCs?')]))=='E nos últimos 6 meses?'
    assert resolve_followup('Agora considere o FEC.',build_memory_context([entry('Compare DEC e FEC nos últimos 6 meses.')]))=='Agora considere o FEC.'


def test_user_definition_required_not_assistant_claim():
    assert financial_clarification('Quais gastos?', 'Usuário: Qual o DEC?\nAssistente: Gastos são faturamento.')
    assert financial_clarification('Quais gastos?', 'Usuário: Gastos são valores das faturas\nAssistente: Certo.') is None


def test_geographic_catalog_requires_confirmation_without_parent(tmp_path):
    path=tmp_path/'geo.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE dim_uc(municipio TEXT,bairro TEXT)')
        c.executemany('INSERT INTO dim_uc VALUES (?,?)',[('Abreu e Lima','Caetés I'),('Abreu e Lima','Caetés II')])
    assert geographic_clarification('Quantas UCs em Caetés entre 2025-07 e 2026-06?',str(path))
    assert geographic_clarification('Quantas UCs em Caetés I no município de Abreu e Lima?',str(path)) is None


@pytest.mark.parametrize("block_second", [False, True])
def test_http_dec12_dec6_fec6_with_real_sql_guardrails_and_audit(monkeypatch,tmp_path,block_second):
    from app.agent import pipeline,sql_generator,answer_synthesizer,sql_executor
    from app.agent.state.dependencies import AgentStateDependencies
    from app.agent.state.sqlite_audit import SQLiteAuditStore
    from app.routers import ia
    path=tmp_path/'gold.db';audit_path=tmp_path/'portal.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE dec_fec_alimentador_mensal(alimentador TEXT,mes_referencia TEXT,dec_horas REAL,fec REAL,dec_12m_horas REAL)')
        c.executemany('INSERT INTO dec_fec_alimentador_mensal VALUES (?,?,?,?,?)',[('AL1',m,1,2,12) for m in [f'2025-{m:02}' for m in range(7,13)]+[f'2026-{m:02}' for m in range(1,7)]])
    class Memory:
        entries=[]
        async def get_context(self,session):return list(self.entries)
        async def append(self,session,value):self.entries.append(value)
    memory=Memory();seen=[]
    async def generate(prompt,**kwargs):
        question=prompt.split('<user_question>\n')[1].split('\n</user_question>')[0]
        seen.append(question)
        if len(seen)==1:
            sql="SELECT alimentador,dec_12m_horas AS dec_horas FROM dec_fec_alimentador_mensal WHERE mes_referencia='2026-06' ORDER BY dec_horas DESC"
        else:
            assert '6 meses' in question and 'alimentadores' in question
            metric='dec_horas' if len(seen)==2 else 'fec'
            assert ('DEC' if len(seen)==2 else 'FEC') in question
            sql=f"SELECT alimentador,SUM({metric}) AS {metric} FROM dec_fec_alimentador_mensal WHERE mes_referencia BETWEEN '2026-01' AND '2026-06' GROUP BY alimentador ORDER BY {metric} DESC"
        return SQLGenerationResult(status=SQLGenerationStatus.READY,sql=sql),[],None
    async def synthesize(prompt,**kwargs):
        value=99999 if block_second and len(seen)==2 else (6 if len(seen)==2 else 12)
        return SynthesisResult(status=SynthesisStatus.ANSWERED,answer=f'O indicador é {value}.'),[],None
    monkeypatch.setattr(sql_generator,'run_with_fallback',generate)
    monkeypatch.setattr(answer_synthesizer,'run_with_fallback',synthesize)
    monkeypatch.setattr(sql_executor,'settings',replace(sql_executor.settings,sqlite_path=str(path)))
    monkeypatch.setattr(pipeline,'get_state_dependencies',lambda:AgentStateDependencies(memory_store=memory,audit_store=SQLiteAuditStore(str(audit_path))))
    app=FastAPI();app.include_router(ia.router);client=TestClient(app)
    for question in ['Quais alimentadores tiveram pior DEC nos últimos 12 meses?','E nos últimos 6 meses?','Agora considere o FEC.']:
        response=client.post('/api/ia/perguntar',json={'pergunta':question,'sessao_id':'synthetic'})
        assert response.status_code==200
        assert response.json()['status']==('nao_sei' if block_second and len(seen)==2 else 'ok')
    assert len(memory.entries)==3
    with sqlite3.connect(audit_path) as c:
        assert c.execute("SELECT COUNT(*) FROM agent_audit WHERE outcome='answered'").fetchone()[0]==(2 if block_second else 3)
    before=len(seen)
    response=client.post('/api/ia/perguntar',json={'pergunta':'Quais os meses com maiores gastos?','sessao_id':'synthetic'})
    assert response.json()['status']=='nao_sei' and len(seen)==before


def test_blocked_turn_preserves_user_period_without_reusing_rejected_content():
    from app.agent.state.records import build_memory_entry
    blocked=build_memory_entry(question='E nos últimos 6 meses?',answer='Resposta não aprovada.',outcome=AgentOutcome.OUTPUT_BLOCKED)
    assert blocked is not None
    assert blocked.answer == "Intenção pendente; nenhuma resposta foi aprovada."
    context=build_memory_context([entry('Quais alimentadores tiveram pior DEC nos últimos 12 meses?'),blocked])
    assert resolve_followup('Agora considere o FEC',context)=='Quais alimentadores tiveram pior FEC nos últimos 6 meses?'


def test_chart_delta_needs_valid_anchor():
    context=build_memory_context([entry('Quais alimentadores tiveram pior FEC nos últimos 6 meses?')])
    assert resolve_followup('Pode exibir um gráfico disso?',context)=='Quais alimentadores tiveram pior FEC nos últimos 6 meses?'
    assert resolve_followup('Pode exibir um gráfico disso?',None)=='Pode exibir um gráfico disso?'


def test_uncovered_municipality_is_not_zero(tmp_path):
    path=tmp_path/'geo.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE dim_uc(municipio TEXT,bairro TEXT)')
        c.execute("INSERT INTO dim_uc VALUES ('Recife','Centro')")
    assert 'não comprova zero' in geographic_clarification('Quantas UCs em Município de Local Inexistente?',str(path))
    assert geographic_clarification('Quantas UCs em Recife?',str(path)) is None


@pytest.mark.parametrize('column',['dec_12m_horas','fec_12m'])
def test_different_window_cannot_execute_rolling_12m(monkeypatch,column):
    from app.agent import sql_generator
    async def provider(*args,**kwargs):
        return SQLGenerationResult(status=SQLGenerationStatus.READY,sql=f'SELECT {column} FROM dec_fec_alimentador_mensal'),[],None
    monkeypatch.setattr(sql_generator,'run_with_fallback',provider)
    generation,_,error=asyncio.run(sql_generator.generate_sql(question='Quais alimentadores tiveram pior DEC nos últimos 6 meses?',database_context='Contrato sintético'))
    assert error is None and generation.status==SQLGenerationStatus.NEEDS_CLARIFICATION


def test_chart_cannot_reuse_blocked_turn():
    context=build_memory_context([entry('Quais alimentadores tiveram pior FEC nos últimos 6 meses?',AgentOutcome.OUTPUT_BLOCKED)])
    assert resolve_followup('Pode exibir um gráfico disso?',context)=='Pode exibir um gráfico disso?'


@pytest.mark.parametrize('session,version,outcome,has_chart,expected',[
 ('same','v1',AgentOutcome.ANSWERED,True,True),
 ('other','v1',AgentOutcome.ANSWERED,True,False),
 ('same','v2',AgentOutcome.ANSWERED,True,False),
 ('same','v1',AgentOutcome.OUTPUT_BLOCKED,True,False),
 ('same','v1',AgentOutcome.ANSWERED,False,False),
])
def test_chart_followup_reuses_only_approved_same_session_version(monkeypatch,session,version,outcome,has_chart,expected):
    from app.agent import pipeline
    from app.agent.schemas import VisualizationSpec,VisualizationPoint,VisualizationType
    from app.agent.state.dependencies import AgentStateDependencies
    chart=VisualizationSpec(type=VisualizationType.BAR,title='FEC',points=[VisualizationPoint(label='AL1',value=2)])
    previous=MemoryEntry(question='Ranking FEC',answer='Indicador aprovado.',outcome=outcome,approved_visualization=chart if has_chart else None,data_version=version)
    class Memory:
        async def get_context(self,key):return [previous] if key=='same' else []
        async def append(self,*args):pass
    async def forbidden(*args,**kwargs):pytest.fail('Gráfico referencial não deve chamar SQL/LLM')
    monkeypatch.setattr(pipeline,'generate_validate_and_execute',forbidden)
    result=asyncio.run(pipeline.answer_question('Pode exibir um gráfico disso?',session_id=session,state_dependencies=AgentStateDependencies(memory_store=Memory(),data_version='v1')))
    assert (result.visualization==chart)==expected
    assert result.outcome==(AgentOutcome.ANSWERED if expected else AgentOutcome.NEEDS_CLARIFICATION)
