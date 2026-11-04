"""Redis real, C4.2/C5 reais e doubles explícitos de LLM/SQL; sem consultar Gold."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[3]
MODULES = {
    "app.agent.state.cache_eligibility": "backend/app/agent/state/cache_eligibility.py",
    "app.agent.state.redis_cache": "backend/app/agent/state/redis_cache.py",
    "app.agent.state.finalizer": "backend/app/agent/state/finalizer.py",
    "app.agent.state.request_state": "backend/app/agent/state/request_state.py",
}
script = "import sys,types,importlib\nfrom app.core.config import settings\n"
for name, path in MODULES.items():
    source = (ROOT / path).read_text(encoding="utf-8")
    script += f"module=types.ModuleType({name!r});sys.modules[{name!r}]=module;exec({source!r},module.__dict__)\n"
script += r'''
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
B = 'Quais alimentadores tiveram pior DEC?'
AMBIGUOUS = 'Quais os 3 meses com maiores gastos?'
SQL_A = 'SELECT mes_referencia, receita_total AS valor_faturado FROM kpis_mensal ORDER BY valor_faturado DESC LIMIT 3'
SQL_B = 'SELECT alimentador, dec_horas FROM dec_fec_alimentador_mensal ORDER BY dec_horas DESC LIMIT 3'
async def validate():
    root = 'diagnostic-eligibility-' + uuid.uuid4().hex
    sessions = [root, root+'-other', root+'-blocked', root+'-ambiguous', root+'-expired', root+'-cap', root+'-race']
    counters = {'generation':0,'execution':0,'synthesis':0}
    records = []
    blocked = False
    class Audit:
        async def save(self, record): records.append(record)
    async def generate(prompt, **kwargs):
        counters['generation'] += 1
        if 'maiores gastos' in prompt:
            return SQLGenerationResult(status=SQLGenerationStatus.NEEDS_CLARIFICATION, reason='Você se refere ao valor faturado ou a despesas operacionais?'), [], None
        sql = SQL_A if 'valores faturados' in prompt else SQL_B
        return SQLGenerationResult(status=SQLGenerationStatus.READY, sql=sql), [], None
    def execute(sql, **kwargs):
        counters['execution'] += 1
        if sql == SQL_A:
            result = QueryExecutionResult(columns=['mes_referencia','valor_faturado'], rows=[['2024-01',100],['2024-03',80],['2024-05',60]], row_count=3)
        else:
            result = QueryExecutionResult(columns=['alimentador','dec_horas'],rows=[['AL1',3],['AL2',2]],row_count=2)
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
                assert len(await memory.get_context(root))==3
                together=await asyncio.gather(*(pipeline.answer_question(A,session_id=root,state_dependencies=deps) for _ in range(3)))
                assert all(r.cache_hit for r in together) and counters==baseline
                assert len(await memory.get_context(root))==3
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
                capped=RedisCacheStore(settings.redis_url,max_entries_per_session=1)
                candidate=build_cache_key(normalized_question=A,session_id=sessions[5],data_version='v',memory_context='before')
                lookup=independent_lookup_key(A,sessions[5],'v')
                value=PostProcessingResult(answer='Fixture aprovada.')
                await capped.set_independent(candidate,value,30,lookup_key=lookup,eligibility=prove_independence(A,SQL_A))
                nxt=build_cache_key(normalized_question=B,session_id=sessions[5],data_version='v')
                await capped.set(nxt,value,30)
                assert not await redis.exists(candidate) and not await redis.exists(lookup)
                print(json.dumps({'redis_real':True,'approved_A_immediate_hit':True,'A_B_A_hit':True,'no_sql_generation_execution_or_synthesis_on_hit':True,'payload_and_chart_preserved':True,'audit_C7':True,'reference_change_miss':True,'literal_ambiguous_A_requires_clarification':True,'blocked_not_indexed':True,'version_and_session_isolated':True,'expired_miss':True,'concurrent_hits':True,'concurrent_publication':True,'hit_does_not_renew_original_ttl':True,'eviction_removes_pointer':True,'LLM_and_SQL_are_test_doubles':True}))
        finally:
            for session in sessions:
                scope=build_cache_key(normalized_question='x',session_id=session,data_version='v').rsplit(':',1)[0]
                keys=[k async for k in redis.scan_iter(match=scope+':*')]
                if keys:await redis.delete(*keys)
                await redis.delete(build_memory_key(session))
asyncio.run(validate())
'''
result=subprocess.run(['docker','exec','-i','v-energy-grid-360-backend-1','python','-'],input=script,encoding='utf-8',capture_output=True)
print(result.stdout)
if result.returncode:print(result.stderr[-2000:])
raise SystemExit(result.returncode)
