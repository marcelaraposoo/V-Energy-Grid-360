"""Ensaio Docker C7: providers controlados; SQL, guardrails e stores reais.

Enviar por stdin: docker compose exec -T backend python - healthy|offline
Só usa sessões novas de validação e limpa suas chaves Redis. Auditoria permanece.
"""

import asyncio
import json
import sqlite3
import sys
from dataclasses import replace
from uuid import uuid4

from redis.asyncio import Redis

from app.agent import pipeline, sql_execution_orchestrator, synthesis_orchestrator
from app.agent.schemas import AgentOutcome, MemoryEntry, SQLGenerationResult, SQLGenerationStatus, SynthesisResult, SynthesisStatus
from app.agent.state.dependencies import get_state_dependencies
from app.agent.state.memory_context import build_memory_context
from app.agent.state.redis_memory import build_memory_key
from app.agent.state.sqlite_audit import SQLiteAuditStore
from app.core.config import settings


async def main(mode):
    assert mode in {"healthy", "offline"}
    deps = get_state_dependencies()
    counts = dict(generation=0, synthesis=0, set=0, get=0)
    keys = set()
    cache = deps.cache_store

    class RecordingCache:
        async def get(self, key):
            counts["get"] += 1
            keys.add(key)
            return await cache.get(key)

        async def set(self, key, value, ttl_seconds):
            counts["set"] += 1
            keys.add(key)
            return await cache.set(key, value, ttl_seconds)

    deps = replace(deps, cache_store=RecordingCache())
    async def generate(**kwargs):
        counts["generation"] += 1
        return SQLGenerationResult(
            status=SQLGenerationStatus.READY,
            sql="SELECT classe, COUNT(*) AS qtd_ucs FROM dim_uc GROUP BY classe ORDER BY classe",
        ), [], None

    async def synthesize(**kwargs):
        counts["synthesis"] += 1
        return SynthesisResult(
            status=SynthesisStatus.ANSWERED,
            answer=f"A consulta retornou {kwargs['result'].row_count} classes.",
        ), [], None

    sql_execution_orchestrator.generate_sql = generate
    synthesis_orchestrator.synthesize_answer = synthesize
    session = "validacao-c7-" + uuid4().hex
    limits_session = session + "-limites"
    question = "Validação C7: quantas unidades consumidoras por classe?"

    def audit(result):
        with sqlite3.connect(settings.portal_db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM agent_audit WHERE request_id=?", (result.request_id,)).fetchall()
        assert len(rows) == 1
        record = dict(rows[0])
        assert record["outcome"] == result.outcome.value
        assert record["cache_hit"] == int(result.cache_hit)
        assert record["timestamp"].endswith("+00:00")
        return record

    first = await pipeline.answer_question(question, session_id=session, state_dependencies=deps)
    assert first.outcome == AgentOutcome.ANSWERED and not first.cache_hit
    audit(first)

    if mode == "offline":
        assert counts["get"] == counts["set"] == 0  # UNAVAILABLE impede cache.
        assert audit(first)["sql"] is not None
        print(json.dumps({"mode": mode, "answer_delivered": True, "audit_persisted": True, "cache_bypassed": True}))
        return

    async with Redis.from_url(settings.redis_url) as client:
        try:
            memory = deps.memory_store
            memory_key = build_memory_key(session)
            assert session not in memory_key
            entries = await memory.get_context(session)
            assert len(entries) == 1 and entries[0].answer == first.message
            assert counts["set"] == 1
            # Restaura só a memória desta sessão de teste ao contexto vazio
            # inicial: HIT exige a MESMA pergunta/sessão/contexto/versão.
            await client.delete(memory_key)
            second = await pipeline.answer_question(question, session_id=session, state_dependencies=deps)
            assert second.cache_hit and second.request_id != first.request_id
            hit_record = audit(second)
            assert hit_record["sql"] is None and hit_record["row_count"] is None
            assert len(await memory.get_context(session)) == 1
            assert counts == dict(generation=1, synthesis=1, set=1, get=2)

            blocked = await pipeline.answer_question("SELECT * FROM dim_uc", session_id=session, state_dependencies=deps)
            assert blocked.outcome == AgentOutcome.INPUT_BLOCKED
            audit(blocked)
            assert len(await memory.get_context(session)) == 1

            for i in range(25):
                await memory.append(limits_session, MemoryEntry(
                    question=f"Pergunta {i}", answer=f"Resposta {i}", outcome=AgentOutcome.ANSWERED,
                ))
            stored = await memory.get_context(limits_session)
            assert len(stored) == 20 and stored[0].question == "Pergunta 5"
            context = build_memory_context(stored)
            assert "Pergunta 19\n" not in context and "Pergunta 20\n" in context
            assert len(context) <= 4000
            limit_key = build_memory_key(limits_session)
            assert 0 < await client.ttl(limit_key) <= settings.memory_ttl_seconds
            await client.expire(limit_key, 2)
            await memory.append(limits_session, MemoryEntry(
                question="Nova pergunta", answer="Resposta", outcome=AgentOutcome.NO_DATA,
            ))
            assert await client.ttl(limit_key) > 2  # TTL renovado.
            for value in await client.lrange(limit_key, 0, -1):
                assert set(json.loads(value)) == {"question", "answer", "outcome"}

            degraded = await pipeline.answer_question(
                question, state_dependencies=replace(deps, audit_store=SQLiteAuditStore("/dev/null/portal.db")),
            )
            assert degraded.outcome == AgentOutcome.ANSWERED
            print(json.dumps({
                "mode": mode, "miss_sets_once": True, "hit_audited_without_set": True,
                "memory_limit": 20, "context_limit": 5, "ttl_renewed": True,
                "audit_failure_preserves_answer": True,
                "request_ids_distinct": first.request_id != second.request_id,
            }))
        finally:
            await client.delete(build_memory_key(session), build_memory_key(limits_session), *keys)


asyncio.run(main(sys.argv[1]))
