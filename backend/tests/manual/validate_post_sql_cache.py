"""Pipeline atual e Redis real; providers/execução SQL são doubles explícitos."""
from pathlib import Path
import base64
import io
import subprocess
import zipfile
ROOT=Path(__file__).resolve().parents[3]
archive=io.BytesIO()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path in (ROOT/'backend/app').rglob('*'):
        if path.is_file() and path.suffix in {'.py','.md'} and '__pycache__' not in path.parts:
            z.write(path,path.relative_to(ROOT/'backend').as_posix())
encoded=base64.b64encode(archive.getvalue()).decode('ascii')
BODY = r'''
import asyncio, uuid, json
from unittest.mock import patch
from redis.asyncio import Redis
from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
import app.agent.state.service as service
importlib.reload(service)
from app.agent import pipeline, sql_generator, answer_synthesizer, sql_execution_orchestrator
importlib.reload(pipeline)
from app.agent.schemas import *
from app.agent.state.redis_memory import RedisMemoryStore, build_memory_key
from app.agent.state.redis_cache import RedisCacheStore
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.cache_eligibility import *
from app.agent.state.cache_key import build_cache_key
A = 'Quais os 3 meses com maiores valores faturados em todo o histórico da distribuidora, sem filtros adicionais?'
B = 'Quais alimentadores tiveram pior DEC nos últimos 12 meses?'
AMBIGUOUS = 'Quais os 3 meses com maiores gastos?'
SQL_A = 'SELECT mes_referencia, receita_total AS valor_faturado FROM kpis_mensal ORDER BY valor_faturado DESC LIMIT 3'
SQL_B = "SELECT alimentador, dec_12m_horas AS dec FROM dec_fec_alimentador_mensal WHERE mes_referencia = '2026-06' ORDER BY dec DESC LIMIT 10"
async def validate():
    root = 'diagnostic-eligibility-' + uuid.uuid4().hex
    sessions = [root, root+'-other', root+'-blocked', root+'-ambiguous', root+'-expired', root+'-cap', root+'-race']
    counters = {'generation':0,'execution':0,'synthesis':0}
    records = []
    blocked = False
    relative_count = 0
    alternative = False
    class Audit:
        async def save(self, record): records.append(record)
    async def generate(prompt, **kwargs):
        nonlocal relative_count
        counters['generation'] += 1
        question=prompt.split('<user_question>\n',1)[1].split('\n</user_question>',1)[0]
        if 'maiores gastos' in question:
            return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason='Você se refere ao valor faturado ou a despesas operacionais?'), [], None
        sql = SQL_A if 'valores faturados' in question else SQL_B
        if question == B and alternative:
            sql = "SELECT alimentador, SUM(dec_horas) AS dec FROM dec_fec_alimentador_mensal WHERE mes_referencia BETWEEN '2025-07' AND '2026-06' GROUP BY alimentador ORDER BY dec DESC LIMIT 10"
        if question == 'E no mês anterior?':
            relative_count += 1
            sql = SQL_B.replace('2026-06', '2026-05' if relative_count == 1 else '2026-04')
        return SQLGenerationResult(status=SQLGenerationStatus.READY, sql=sql), [], None
    def execute(sql, **kwargs):
        counters['execution'] += 1
        if sql == SQL_A:
            result = QueryExecutionResult(columns=['mes_referencia','valor_faturado'], rows=[['2024-01',100],['2024-03',80],['2024-05',60]], row_count=3)
        else:
            result = QueryExecutionResult(columns=['alimentador','dec'],rows=[['AL1',3],['AL2',2]],row_count=2)
        return SQLExecutionOutcome(status=SQLExecutionStatus.SUCCESS,result=result)
    async def synthesize(prompt, **kwargs):
        counters['synthesis'] += 1
        if blocked: answer='https://example.invalid'
        elif 'valor_faturado' in prompt: answer='Os valores faturados foram R$ 100 em janeiro de 2024, R$ 80 em março de 2024 e R$ 60 em maio de 2024.'
        else: answer='Os valores de DEC retornados são 3 h e 2 h.'
        return SynthesisResult(status=SynthesisStatus.ANSWERED,answer=answer,assumptions=['Todo o histórico do snapshot.']), [], None
    cache=RedisCacheStore(settings.redis_url,max_entries_per_session=5)
    memory=RedisMemoryStore(settings.redis_url)
    deps=AgentStateDependencies(audit_store=Audit(),cache_store=cache,memory_store=memory,data_version='synthetic-fixed-v1',cache_ttl_seconds=30)
    def pointer(session,version='synthetic-fixed-v1'):return independent_lookup_key(A,session,version)
    async with Redis.from_url(settings.redis_url) as redis:
        try:
            with patch.object(sql_generator,'run_with_fallback',generate),patch.object(answer_synthesizer,'run_with_fallback',synthesize),patch.object(sql_execution_orchestrator,'execute_sql',execute),patch.object(pipeline,'load_database_context',lambda:'Contrato sintético.'):
                first=await pipeline.answer_question(A,session_id=root,state_dependencies=deps)
                assert first.outcome==AgentOutcome.ANSWERED and not first.cache_hit, ('first',first.outcome)
                key=pointer(root)
                assert await redis.exists(key), 'pointer absent'
                target=await redis.get(key)
                raw=json.loads(await redis.get(target))
                assert raw['_cache_format']=='c2-independent-v1' and raw['eligibility']['intent_hash']
                assert await redis.pttl(key)<=await redis.pttl(target)+5
                pointer_ttl_before=await redis.pttl(key)
                target_ttl_before=await redis.pttl(target)
                baseline=dict(counters)
                immediate=await pipeline.answer_question(A,session_id=root,state_dependencies=deps)
                assert immediate.cache_hit and counters==baseline, 'immediate miss'
                assert await redis.pttl(key)<=pointer_ttl_before and await redis.pttl(target)<=target_ttl_before
                await pipeline.answer_question(B,session_id=root,state_dependencies=deps)
                baseline=dict(counters)
                repeated=await pipeline.answer_question(A,session_id=root,state_dependencies=deps)
                assert repeated.cache_hit and counters==baseline, 'A B A miss'
                assert repeated.message==first.message and repeated.assumptions==first.assumptions and repeated.visualization==first.visualization
                assert records[-1].cache_hit and records[-1].sql is None
                before_b=dict(counters)
                repeated_b=await pipeline.answer_question(B,session_id=root,state_dependencies=deps)
                assert repeated_b.cache_hit and counters['generation']==before_b['generation']+1
                assert counters['execution']==before_b['execution'] and counters['synthesis']==before_b['synthesis']
                assert records[-1].cache_hit and records[-1].sql is None
                before_b=dict(counters)
                consecutive_b=await pipeline.answer_question(B,session_id=root,state_dependencies=deps)
                assert consecutive_b.cache_hit
                assert counters['execution']==before_b['execution'] and counters['synthesis']==before_b['synthesis']
                assert len(await memory.get_context(root))<=5
                together=await asyncio.gather(*(pipeline.answer_question(A,session_id=root,state_dependencies=deps) for _ in range(3)))
                assert all(r.cache_hit for r in together) and counters['execution']==before_b['execution'] and counters['synthesis']==before_b['synthesis']
                assert len(await memory.get_context(root))<=5
                alternative=True
                variant=await pipeline.answer_question(B,session_id=root,state_dependencies=deps)
                assert not variant.cache_hit
                await pipeline.answer_question(A,session_id=root,state_dependencies=deps)
                before_variant=dict(counters)
                assert (await pipeline.answer_question(B,session_id=root,state_dependencies=deps)).cache_hit
                assert counters['execution']==before_variant['execution'] and counters['synthesis']==before_variant['synthesis']
                alternative=False
                other=await pipeline.answer_question(A,session_id=sessions[1],state_dependencies=deps)
                assert not other.cache_hit
                from dataclasses import replace
                changed=await pipeline.answer_question(A,session_id=root,state_dependencies=replace(deps,data_version='synthetic-v2'))
                assert not changed.cache_hit
                relative='E no mês anterior?'
                assert resolve_intent(relative) is None
                one=await pipeline.answer_question(relative,session_id=root,state_dependencies=deps)
                await pipeline.answer_question(B,session_id=root,state_dependencies=deps)
                two=await pipeline.answer_question(relative,session_id=root,state_dependencies=deps)
                assert not one.cache_hit and not two.cache_hit
                ambiguous=await pipeline.answer_question(AMBIGUOUS,session_id=sessions[3],state_dependencies=deps)
                assert ambiguous.outcome==AgentOutcome.NEEDS_CLARIFICATION and not ambiguous.cache_hit
                assert not await redis.exists(pointer(sessions[3]))
                blocked=True
                rejected=await pipeline.answer_question(A,session_id=sessions[2],state_dependencies=deps)
                assert rejected.outcome==AgentOutcome.OUTPUT_BLOCKED
                assert not await redis.exists(pointer(sessions[2]))
                blocked=False
                expdeps=replace(deps,cache_ttl_seconds=1)
                await pipeline.answer_question(A,session_id=sessions[4],state_dependencies=expdeps)
                await asyncio.sleep(1.1)
                expired=await pipeline.answer_question(A,session_id=sessions[4],state_dependencies=expdeps)
                assert not expired.cache_hit
                raced=await asyncio.gather(*(pipeline.answer_question(A,session_id=sessions[6],state_dependencies=deps) for _ in range(3)))
                assert all(item.outcome==AgentOutcome.ANSWERED for item in raced)
                before_race_hit=dict(counters)
                assert (await pipeline.answer_question(A,session_id=sessions[6],state_dependencies=deps)).cache_hit
                assert counters==before_race_hit
                assert await redis.pttl(pointer(sessions[6]))>0
                from app.agent.state.sql_cache import sql_cache_plan
                renamed_sql=SQL_B.replace('AS dec','AS dec_apresentacao').replace('ORDER BY dec DESC','ORDER BY dec_apresentacao DESC')
                assert sql_cache_plan(B,renamed_sql,root,deps.data_version)==sql_cache_plan(B,SQL_B,root,deps.data_version)
                plan_store=RedisCacheStore(settings.redis_url,max_entries_per_session=1)
                plan=sql_cache_plan(B,SQL_B,sessions[5],'v')
                original=build_cache_key(normalized_question=B,session_id=sessions[5],data_version='v',memory_context='original')
                plan_value=PostProcessingResult(answer='Fixture de plano aprovada.', assumptions=['Snapshot sintético.'])
                await plan_store.set_approved(original,plan_value,1,plan=plan)
                assert (await plan_store.get_plan(plan.lookup,digest=plan.digest)).response==plan_value
                wrong_target=build_cache_key(normalized_question=B,session_id=sessions[0],data_version='v')
                await redis.set(plan.lookup,wrong_target,ex=1)
                assert not (await plan_store.get_plan(plan.lookup,digest=plan.digest)).cache_hit
                await plan_store.set_approved(original,plan_value,1,plan=plan)
                await redis.set(original,'invalid-payload',keepttl=True)
                assert (await plan_store.get_plan(plan.lookup,digest=plan.digest)).reason=='payload_invalid'
                await plan_store.set_approved(original,plan_value,1,plan=plan)
                await asyncio.sleep(1.1)
                assert not (await plan_store.get_plan(plan.lookup,digest=plan.digest)).cache_hit
                await plan_store.set_approved(original,plan_value,30,plan=plan)
                other_key=build_cache_key(normalized_question='Outra fixture',session_id=sessions[5],data_version='v')
                await plan_store.set(other_key,plan_value,30)
                assert not await redis.exists(original) and not await redis.exists(plan.lookup)
                capped=RedisCacheStore(settings.redis_url,max_entries_per_session=1)
                candidate=build_cache_key(normalized_question=A,session_id=sessions[5],data_version='v',memory_context='before')
                lookup=independent_lookup_key(A,sessions[5],'v')
                value=PostProcessingResult(answer='Fixture aprovada.')
                await capped.set_independent(candidate,value,30,lookup_key=lookup,eligibility=prove_independence(A,SQL_A))
                nxt=build_cache_key(normalized_question=B,session_id=sessions[5],data_version='v')
                await capped.set(nxt,value,30)
                assert not await redis.exists(candidate) and not await redis.exists(lookup)
                print(json.dumps({'redis_real':True,'approved_A_immediate_hit':True,'A_B_A_hit':True,'pre_sql_A_hit_skips_all_expensive_stages':True,'payload_and_chart_preserved':True,'audit_C7':True,'reference_change_miss':True,'literal_ambiguous_A_requires_clarification':True,'blocked_not_indexed':True,'version_and_session_isolated':True,'expired_miss':True,'concurrent_hits':True,'concurrent_publication':True,'hit_does_not_renew_original_ttl':True,'eviction_removes_pointer':True,'LLM_and_SQL_are_test_doubles':True,'A_B_A_B_hits':True,'B_hit_after_generation_only':True,'consecutive_B_hit':True,'different_SQL_forms_remain_distinct':True,'plan_expiry_invalid_payload_foreign_scope_and_eviction':True,'output_alias_binding_equivalence':True}))
        finally:
            for session in sessions:
                scope=build_cache_key(normalized_question='x',session_id=session,data_version='v').rsplit(':',1)[0]
                keys=[k async for k in redis.scan_iter(match=scope+':*')]
                if keys:await redis.delete(*keys)
                await redis.delete(build_memory_key(session))
asyncio.run(validate())
'''
script="import base64,io,zipfile,tempfile,sys,importlib\n"
script+="with tempfile.TemporaryDirectory(prefix='c2-plan-contract-') as folder:\n"
script+=f"    zipfile.ZipFile(io.BytesIO(base64.b64decode({encoded!r}))).extractall(folder)\n"
script+="    sys.path.insert(0,folder)\n"
script+="    from app.core.config import settings\n"
script+=f"    exec({BODY!r})\n"
result=subprocess.run(['docker','exec','-i','v-energy-grid-360-backend-1','python','-'],input=script,encoding='utf-8',capture_output=True)
print(result.stdout)
if result.returncode: print(result.stderr[-2000:])
raise SystemExit(result.returncode)
