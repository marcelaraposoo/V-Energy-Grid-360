"""Contrato Redis real isolado, sem providers ou Gold; executar da raiz do repo."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
source = (ROOT / "backend/app/agent/state/cache_key.py").read_text(encoding="utf-8")
source += "\n" + (ROOT / "backend/app/agent/state/redis_cache.py").read_text(encoding="utf-8")
source += "\n" + (ROOT / "backend/app/agent/state/redis_memory.py").read_text(encoding="utf-8")
source += r'''
import uuid, json
from app.core.config import settings
async def validate():
    session = "diagnostic-bounded-" + uuid.uuid4().hex
    keys = [build_cache_key(normalized_question=str(i), session_id=session, data_version="synthetic") for i in range(12)]
    other = build_cache_key(normalized_question="other", session_id=session+"-other", data_version="synthetic")
    buckets = {key.rsplit(":", 1)[0] + ":entries" for key in keys + [other]}
    store = RedisCacheStore(settings.redis_url, max_entries_per_session=3)
    value = PostProcessingResult(answer="Fixture sintética.", assumptions=["Isolada."])
    async with store._client() as client:
        try:
            memory = RedisMemoryStore(settings.redis_url)
            entry = MemoryEntry(question="Fixture A?", answer="A.", outcome=__import__('app.agent.schemas',fromlist=['AgentOutcome']).AgentOutcome.ANSWERED)
            await asyncio.gather(*(memory.append(session, entry) for _ in range(10)))
            assert len(await memory.get_context(session)) == 1
            await memory.append(session, entry.model_copy(update={"question":"Fixture B?"}))
            await memory.append(session, entry)
            assert len(await memory.get_context(session)) == 3
            await asyncio.gather(*(store.set(key, value, 30) for key in keys))
            assert sum([await client.exists(key) for key in keys]) == 3
            assert await client.zcard(next(iter(buckets - {other.rsplit(":",1)[0]+":entries"}))) == 3
            await store.set(other, value, 30)
            assert await store.get(other) == value
            ttl = await client.pttl(other)
            assert await store.get(other) == value
            assert 0 < await client.pttl(other) <= ttl
            # Expiração usa TTL real do Redis, sem possibilidade de ressuscitar.
            await store.set(other, value, 1)
            await asyncio.sleep(1.1)
            assert await store.get(other) is None
            print(json.dumps({"atomic_concurrent_limit": True, "session_isolation": True, "payload_preserved": True, "get_does_not_renew_ttl": True, "expired_is_miss": True, "atomic_memory_deduplication": True, "context_turn_after_other_question": True}))
        finally:
            await client.delete(*keys, other, *buckets, build_memory_key(session))
asyncio.run(validate())
'''
result = subprocess.run(["docker", "exec", "-i", "v-energy-grid-360-backend-1", "python", "-"], input=source, encoding="utf-8", capture_output=True)
print(result.stdout)
if result.returncode:
    print("Validação Redis falhou; nenhuma credencial será exibida.")
raise SystemExit(result.returncode)
