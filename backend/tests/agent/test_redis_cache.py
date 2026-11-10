import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest
from redis.exceptions import ConnectionError

from app.agent.schemas import PostProcessingResult
from app.agent.state.redis_cache import RedisCacheStore


@pytest.fixture
def client(monkeypatch):
    client = AsyncMock()
    client.__aenter__.return_value = client
    factory = Mock(return_value=client)
    monkeypatch.setattr("app.agent.state.redis_cache.Redis.from_url", factory)
    return client, factory


def test_get_revalidates_json_and_closes_client(client):
    redis, factory = client
    redis.get.return_value = b'{"answer":"Resposta aprovada.","assumptions":[]}'
    store = RedisCacheStore("redis://redis:6379/0")

    value = asyncio.run(store.get("key"))

    assert value == PostProcessingResult(answer="Resposta aprovada.")
    redis.get.assert_awaited_once_with("key")
    redis.__aexit__.assert_awaited_once()
    options = factory.call_args.kwargs
    assert options["socket_timeout"] == options["socket_connect_timeout"] == 1


@pytest.mark.parametrize("payload", [None, b"invalido", b"{}", b'{"answer":12}',
    b'{"answer":"ok","assumptions":"antigo"}'])
def test_invalid_or_absent_payload_is_miss(client, payload):
    redis, _ = client
    redis.get.return_value = payload

    assert asyncio.run(RedisCacheStore("redis://redis").get("key")) is None


def test_set_serializes_only_final_result_and_expires(client):
    redis, _ = client
    value = PostProcessingResult(answer="Resposta.")

    asyncio.run(RedisCacheStore("redis://redis").set("key", value, 300))

    args, kwargs = redis.eval.await_args
    assert args[1:4] == (2, "key", "key:entries")
    assert json.loads(args[4]) == value.model_dump(mode="json")
    assert set(json.loads(args[4])) == {"answer", "assumptions", "visualization", "source_sql", "interpretation"}
    assert args[5:] == (300, 100)
    assert kwargs == {}
    redis.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("operation", ["get", "set"])
@pytest.mark.parametrize("failure", ["connection", "timeout"])
def test_redis_failures_degrade_safely(client, operation, failure, caplog):
    redis, _ = client
    command = getattr(redis, "eval" if operation == "set" else operation)
    if failure == "connection":
        command.side_effect = ConnectionError("segredo-na-url")
    else:
        async def hang(*args, **kwargs):
            await asyncio.Event().wait()
        command.side_effect = hang

    async def run():
        store = RedisCacheStore("redis://redis", timeout_seconds=0.01)
        if operation == "get":
            return await store.get("key")
        return await store.set("key", PostProcessingResult(answer="Resposta."), 300)

    assert asyncio.run(asyncio.wait_for(run(), 1)) is None
    assert "segredo-na-url" not in caplog.text


def test_cancellation_is_not_swallowed(client):
    redis, _ = client
    redis.get.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(RedisCacheStore("redis://redis").get("key"))


def test_each_operation_owns_a_client_even_across_event_loops(client):
    redis, factory = client
    redis.get.return_value = None
    store = RedisCacheStore("redis://redis")
    asyncio.run(store.get("a"))
    asyncio.run(store.set("a", PostProcessingResult(answer="Resposta."), 300))
    assert factory.call_count == 2
    assert redis.__aexit__.await_count == 2


@pytest.mark.parametrize("failure", ["connection", "invalid_payload", "wrong_intent", "wrong_contract"])
def test_independent_lookup_fails_closed(client, failure, caplog):
    from app.agent.state.cache_eligibility import independent_lookup_key, resolve_intent, intent_digest, prove_independence
    question = "Quais os 3 meses com maiores valores faturados em todo o histórico da distribuidora, sem filtros adicionais?"
    sql = "SELECT mes_referencia, receita_total FROM kpis_mensal ORDER BY receita_total DESC LIMIT 3"
    lookup = independent_lookup_key(question, "s", "v")
    proof = prove_independence(question, sql)
    redis, _ = client
    if failure == "connection":
        redis.eval.side_effect = ConnectionError("PRIVATE_TOKEN")
    else:
        metadata = {**proof.metadata(), "lookup": lookup}
        if failure == "wrong_intent": metadata["intent_hash"] = "0" * 64
        if failure == "wrong_contract": metadata["contract"] = "unknown"
        envelope = {"_cache_format": "c2-independent-v1", "eligibility": metadata,
                    "response": {"answer": 123} if failure == "invalid_payload" else {"answer": "Fixture."}}
        redis.eval.return_value = ["target", json.dumps(envelope)]
    value = asyncio.run(RedisCacheStore("redis://redis").get_independent(lookup, intent_hash=intent_digest(resolve_intent(question))))
    assert value is None
    assert "PRIVATE_TOKEN" not in caplog.text


@pytest.mark.parametrize("failure,reason", [
    ("absent", "not_found_or_expired"),
    ("invalid_json", "payload_invalid"),
    ("invalid_response", "payload_invalid"),
    ("wrong_contract", "plan_mismatch"),
    ("wrong_digest", "plan_mismatch"),
    ("connection", "redis_error"),
])
def test_plan_lookup_fails_closed(client, failure, reason, caplog):
    from app.agent.state.sql_cache import sql_cache_plan
    plan = sql_cache_plan("Pergunta sintética", "SELECT COUNT(*) AS total FROM dim_uc", "s", "v")
    redis, _ = client
    envelope = {"_cache_format": "c2-plan-v1", "plan": plan.metadata(),
                "response": {"answer": "Fixture aprovada.", "assumptions": ["Fixture."]}}
    if failure == "connection":
        redis.eval.side_effect = ConnectionError("PRIVATE_SECRET")
    elif failure == "absent":
        redis.eval.return_value = None
    elif failure == "invalid_json":
        redis.eval.return_value = ["target", "invalid"]
    else:
        if failure == "invalid_response":
            envelope["response"]["answer"] = 12
        elif failure == "wrong_contract":
            envelope["plan"]["contract"] = "other"
        elif failure == "wrong_digest":
            envelope["plan"]["digest"] = "0" * 64
        redis.eval.return_value = ["target", json.dumps(envelope)]
    result = asyncio.run(RedisCacheStore("redis://redis").get_plan(plan.lookup, digest=plan.digest))
    assert not result.cache_hit and result.reason == reason
    assert "PRIVATE_SECRET" not in caplog.text


def test_plan_hit_preserves_payload_and_never_writes(client):
    from app.agent.state.sql_cache import sql_cache_plan
    plan = sql_cache_plan("Pergunta sintética", "SELECT COUNT(*) AS total FROM dim_uc", "s", "v")
    value = PostProcessingResult(answer="Fixture.", assumptions=["Escopo sintético."])
    redis, _ = client
    redis.eval.return_value = ["target", json.dumps({
        "_cache_format": "c2-plan-v1", "plan": plan.metadata(),
        "response": value.model_dump(mode="json"),
    })]
    result = asyncio.run(RedisCacheStore("redis://redis").get_plan(plan.lookup, digest=plan.digest))
    assert result.response == value and result.reason == "hit"
    script = redis.eval.await_args.args[0]
    assert "SET" not in script and "EXPIRE" not in script


def test_plan_pointer_cannot_be_published_in_another_session(client):
    from app.agent.state.cache_key import build_cache_key
    from app.agent.state.sql_cache import sql_cache_plan
    redis, _ = client
    key = build_cache_key(normalized_question="Fixture", session_id="s1", data_version="v")
    plan = sql_cache_plan("Fixture", "SELECT COUNT(*) FROM dim_uc", "s2", "v")
    asyncio.run(RedisCacheStore("redis://redis").set_approved(
        key, PostProcessingResult(answer="Fixture."), 300, plan=plan,
    ))
    redis.eval.assert_not_awaited()
