"""Validação controlada dentro do backend Docker, sem credenciais de providers.

Enviar por stdin: docker compose exec -T backend python - healthy|offline
Geração/síntese são determinísticas; SQL, guardrails, C6 e Redis são reais.
Não altera Gold/portal, não usa FLUSHDB e remove somente suas próprias chaves.
"""

import asyncio
import json
import sys
from dataclasses import replace
from uuid import uuid4

from redis.asyncio import Redis

from app.agent import pipeline, sql_execution_orchestrator, synthesis_orchestrator
from app.agent.schemas import (
    AgentOutcome, PostProcessingResult, SQLGenerationResult, SQLGenerationStatus,
    SynthesisResult, SynthesisStatus,
)
from app.agent.state.dependencies import get_state_dependencies
from app.core.config import settings


async def main(mode):
    assert mode in {"healthy", "offline"}
    counts = dict(generation=0, sql_guardrail=0, execution=0, synthesis=0,
                  output_guardrail=0, post_processing=0, get=0, set=0)
    sql = "SELECT classe, COUNT(*) AS qtd_ucs FROM dim_uc GROUP BY classe ORDER BY classe"

    async def generate(**kwargs):
        counts["generation"] += 1
        return SQLGenerationResult(status=SQLGenerationStatus.READY, sql=sql), [], None

    async def synthesize(**kwargs):
        counts["synthesis"] += 1
        result = kwargs["result"]
        return SynthesisResult(
            status=SynthesisStatus.ANSWERED,
            answer=f"A consulta retornou {result.row_count} classes.",
        ), [], None

    def spy(module, name, counter):
        original = getattr(module, name)
        def call(*args, **kwargs):
            counts[counter] += 1
            return original(*args, **kwargs)
        setattr(module, name, call)

    sql_execution_orchestrator.generate_sql = generate
    synthesis_orchestrator.synthesize_answer = synthesize
    spy(sql_execution_orchestrator, "validate_sql", "sql_guardrail")
    spy(sql_execution_orchestrator, "execute_sql", "execution")
    spy(synthesis_orchestrator, "validate_output", "output_guardrail")
    spy(pipeline, "process_approved_response", "post_processing")
    # Ensaio isolado da C2: fixa contexto e não grava auditoria do portal.
    deps = replace(get_state_dependencies(), memory_store=None, audit_store=None)
    store = deps.cache_store
    keys = []

    class RecordingStore:
        async def get(self, key):
            counts["get"] += 1
            keys.append(key)
            return await store.get(key)

        async def set(self, key, value, ttl_seconds):
            counts["set"] += 1
            assert key == keys[-1]
            return await store.set(key, value, ttl_seconds)

    deps = replace(deps, cache_store=RecordingStore())
    session = "validacao-c2-" + uuid4().hex
    question = "Quantas unidades consumidoras por classe?"
    first = await pipeline.answer_question(question, session_id=session, state_dependencies=deps)
    assert first.outcome == AgentOutcome.ANSWERED and not first.cache_hit
    assert counts["set"] == 1

    if mode == "offline":
        second = await pipeline.answer_question(question, session_id=session, state_dependencies=deps)
        assert second.outcome == AgentOutcome.ANSWERED and not second.cache_hit
        assert first.message == second.message
        assert all(counts[name] == 2 for name in counts)
        print(json.dumps({"mode": mode, "approved_responses": 2, "counts": counts}))
        return

    async with Redis.from_url(settings.redis_url) as client:
        try:
            key = keys[0]
            ttl_before = await client.ttl(key)
            assert 0 < ttl_before <= deps.cache_ttl_seconds
            payload = json.loads(await client.get(key))
            assert set(payload) == {"answer", "assumptions", "visualization"}
            assert "sql" not in payload and "request_id" not in payload
            assert all(len(part) == 64 for part in key.removeprefix("agent:answer:v4:").split(":"))
            second = await pipeline.answer_question(question, session_id=session, state_dependencies=deps)
            assert second.cache_hit and second.outcome == AgentOutcome.ANSWERED
            assert first.request_id != second.request_id
            assert second.sql is None and second.provider_attempts == ()
            assert first.message == second.message
            assert first.visualization == second.visualization
            assert counts["get"] == 2 and counts["set"] == 1
            assert all(counts[name] == 1 for name in counts if name not in {"get", "set"})

            await client.set(key, "JSON invalido", ex=300)
            assert await store.get(key) is None
            await store.set(key, PostProcessingResult(answer="Resposta temporaria."), 1)
            await asyncio.sleep(1.1)
            assert await store.get(key) is None
            print(json.dumps({
                "mode": mode, "miss_then_hit": True, "ttl_seconds": ttl_before,
                "expiry_and_invalid_payload": "passed", "counts": counts,
            }))
        finally:
            await client.delete(*set(keys))


asyncio.run(main(sys.argv[1]))
