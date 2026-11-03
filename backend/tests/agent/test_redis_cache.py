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
    assert set(json.loads(args[4])) == {"answer", "assumptions", "visualization"}
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
