"""Regressão Redis real: segundo A deve ser HIT. Falha expõe o contrato ainda não atendido.
Executar da raiz; não consulta Gold/providers nem altera sessões existentes.
"""
import subprocess

SCRIPT = r'''
import asyncio,json,uuid
from unittest.mock import patch
from app.agent import pipeline
from app.agent.schemas import *
from app.agent.synthesis_orchestrator import SynthesisFlowResult
from app.agent.guardrails.output_guardrail import validate_output
from app.agent.state.redis_cache import RedisCacheStore
from app.agent.state.redis_memory import RedisMemoryStore,build_memory_key
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.cache_key import build_cache_key
from app.agent.state.memory_context import build_memory_context
from app.core.config import settings
from redis.asyncio import Redis

async def run():
    session='diagnostic-consecutive-'+uuid.uuid4().hex
    question='Quantas unidades há?'
    result=QueryExecutionResult(columns=['total'],rows=[[7]],row_count=1)
    sql='SELECT quantidade AS total FROM resumo_sintetico'
    synthesis=SynthesisResult(status=SynthesisStatus.ANSWERED,answer='Há 7 unidades.')
    guard=validate_output(synthesis.answer,[],question,sql,result)
    assert guard.decision==OutputGuardrailDecision.ALLOW
    calls={'sql_flow':0,'synthesis':0}
    records=[]
    class Audit:
        async def save(self,record):records.append(record)
    async def generate(**kwargs):
        calls['sql_flow']+=1
        return SQLExecutionFlowResult(generation_status=SQLGenerationStatus.READY,sql=sql,outcome=SQLExecutionOutcome(status=SQLExecutionStatus.SUCCESS,result=result))
    async def synthesize(**kwargs):
        calls['synthesis']+=1
        return SynthesisFlowResult(synthesis=synthesis,guardrail=guard,provider_attempts=[],provider_error=None,regenerations=0)
    memory=RedisMemoryStore(settings.redis_url)
    cache=RedisCacheStore(settings.redis_url)
    deps=AgentStateDependencies(audit_store=Audit(),memory_store=memory,cache_store=cache,data_version='synthetic-fixed-snapshot',cache_ttl_seconds=settings.cache_ttl_seconds)
    before=build_cache_key(normalized_question=question,session_id=session,data_version=deps.data_version)
    keys={before}
    second_hit=False
    async with Redis.from_url(settings.redis_url) as redis:
        try:
            with patch.object(pipeline,'generate_validate_and_execute',generate),patch.object(pipeline,'synthesize_and_validate',synthesize),patch.object(pipeline,'load_database_context',lambda:'Contrato sintético.'):
                first=await pipeline.answer_question(question,session_id=session,state_dependencies=deps)
                stored=await cache.get(before)
                ttl=await redis.ttl(before)
                entries=await memory.get_context(session)
                after=build_cache_key(normalized_question=question,session_id=session,data_version=deps.data_version,memory_context=build_memory_context(entries))
                keys.add(after)
                baseline=dict(calls)
                second=await pipeline.answer_question(question,session_id=session,state_dependencies=deps)
                second_hit=second.cache_hit
                second_calls=dict(calls)
                third=await pipeline.answer_question(question,session_id=session,state_dependencies=deps)
                print(json.dumps({'first_approved':first.outcome==AgentOutcome.ANSWERED,'set_exists_before_repeat':bool(await redis.exists(before)),'set_valid_before_repeat':stored is not None,'stored_answer_matches_first':stored.answer==first.message if stored else False,'ttl_before_repeat':ttl,'same_session_question_version':True,'memory_changed_cache_identity':before!=after,'second_cache_hit':second_hit,'second_reentered_sql_flow':second_calls['sql_flow']>baseline['sql_flow'],'second_reentered_synthesis':second_calls['synthesis']>baseline['synthesis'],'third_cache_hit':third.cache_hit,'third_did_not_reenter_expensive_stages':calls==second_calls,'audit_outcomes':[r.outcome.value for r in records]}))
        finally:
            buckets={key.rsplit(':',1)[0]+':entries' for key in keys}
            await redis.delete(*keys,*buckets,build_memory_key(session))
    assert second_hit, 'Esperado C2 HIT na segunda pergunta aprovada; observado MISS por identidade dependente da memória.'
asyncio.run(run())
'''
result=subprocess.run(['docker','exec','-i','v-energy-grid-360-backend-1','python','-'],input=SCRIPT,encoding='utf-8',capture_output=True)
print(result.stdout)
if result.returncode:
    print('REGRESSÃO REPRODUZIDA: contrato de HIT imediato ainda não atendido; nenhuma sessão real foi alterada.')
raise SystemExit(result.returncode)
