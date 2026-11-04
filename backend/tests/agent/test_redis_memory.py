import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from app.agent.schemas import AgentOutcome, MemoryEntry
from app.agent.state.redis_memory import (
    CorruptedMemoryError, RedisMemoryStore, build_memory_key, MEMORY_KEY_PREFIX,
)
from app.agent.state.memory_context import build_memory_context


def _entry(number=1, outcome=AgentOutcome.ANSWERED):
    return MemoryEntry(question=f"Pergunta {number}", answer=f"Resposta {number}", outcome=outcome)


@pytest.fixture
def redis(monkeypatch):
    client = AsyncMock()
    client.__aenter__.return_value = client
    transaction = AsyncMock()
    transaction.__aenter__.return_value = transaction
    for name in ("rpush", "ltrim", "expire"):
        setattr(transaction, name, Mock(return_value=transaction))
    client.pipeline = Mock(return_value=transaction)
    monkeypatch.setattr("app.agent.state.redis_memory.create_redis_client", Mock(return_value=client))
    return client, transaction


def test_memory_key_is_deterministic_versioned_and_hides_session():
    key = build_memory_key("sessao-secreta")
    assert key == build_memory_key("sessao-secreta")
    assert key != build_memory_key("outra-sessao")
    assert key.startswith(MEMORY_KEY_PREFIX + ":")
    assert "sessao-secreta" not in key
    assert len(key.removeprefix(MEMORY_KEY_PREFIX + ":")) == 64


def test_append_atomically_limits_storage_and_renews_ttl(redis):
    client, tx = redis
    store = RedisMemoryStore("redis://redis", ttl_seconds=86400)
    asyncio.run(store.append("s1", _entry()))
    asyncio.run(store.append("s1", _entry(2)))
    args = client.eval.await_args.args
    assert args[1:3] == (1, build_memory_key("s1"))
    assert set(json.loads(args[3])) == {"question", "answer", "outcome"}
    assert json.loads(args[3])["answer"] == "Resposta 2"
    assert args[4:] == (20, 86400)
    assert client.eval.await_count == 2
    assert client.__aexit__.await_count == 2



@pytest.mark.parametrize("outcome", list(AgentOutcome))
def test_only_eligible_outcomes_are_appended(redis, outcome):
    client, tx = redis
    asyncio.run(RedisMemoryStore("redis://redis").append("s1", _entry(outcome=outcome)))
    assert client.eval.await_count == int(outcome in {
        AgentOutcome.ANSWERED, AgentOutcome.NO_DATA, AgentOutcome.NEEDS_CLARIFICATION, AgentOutcome.OUTPUT_BLOCKED, AgentOutcome.INSUFFICIENT_CONTEXT,
    })


def test_get_revalidates_last_twenty_and_context_uses_last_five(redis):
    client, _ = redis
    client.lrange.return_value = [_entry(i).model_dump_json().encode() for i in range(1, 21)]
    entries = asyncio.run(RedisMemoryStore("redis://redis").get_context("s1"))
    client.lrange.assert_awaited_once_with(build_memory_key("s1"), -20, -1)
    assert len(entries) == 20
    client.delete.assert_not_awaited()
    context = build_memory_context(entries)
    assert "Pergunta 15\n" not in context and "Pergunta 16\n" in context
    assert "Pergunta 20\n" in context and len(context) <= 4000


@pytest.mark.parametrize("payload", [
    "{}", "JSON invalido", b"\xff", "[]",
    '{"question": 42, "answer": "Resposta", "outcome": "answered"}',
    _entry(outcome=AgentOutcome.PROVIDER_ERROR).model_dump_json(),
])
def test_incompatible_memory_is_deleted_but_not_silently_empty(redis, payload):
    client, _ = redis
    client.lrange.return_value = [payload]
    with pytest.raises(CorruptedMemoryError):
        asyncio.run(RedisMemoryStore("redis://redis").get_context("s1"))
    client.delete.assert_awaited_once_with(build_memory_key("s1"))
    client.pipeline.assert_not_called()


def test_corruption_cleanup_failure_is_safe_and_can_be_retried(redis, caplog):
    client, _ = redis
    client.lrange.return_value = ["JSON invalido confidencial"]
    client.delete.side_effect = [ConnectionError("redis-confidencial"), 1]
    store = RedisMemoryStore("redis://redis")
    for _ in range(2):
        with pytest.raises(CorruptedMemoryError):
            asyncio.run(store.get_context("s1"))
    assert client.delete.await_count == 2
    assert "ConnectionError" in caplog.text
    assert "confidencial" not in caplog.text


@pytest.mark.parametrize("operation", ["read", "append"])
@pytest.mark.parametrize("failure", ["exception", "timeout"])
def test_memory_errors_propagate_to_state_or_finalizer(redis, operation, failure):
    client, tx = redis
    command = client.lrange if operation == "read" else client.eval
    if failure == "exception":
        command.side_effect = ConnectionError("indisponivel")
    else:
        async def hang(*args):
            await asyncio.Event().wait()
        command.side_effect = hang
    store = RedisMemoryStore("redis://redis", timeout_seconds=0.01)
    with pytest.raises((ConnectionError, TimeoutError)):
        asyncio.run(store.get_context("s1") if operation == "read" else store.append("s1", _entry()))
    client.delete.assert_not_awaited()


def test_read_refreshes_inactivity_without_appending(redis):
    client, tx = redis
    client.lrange.return_value = [_entry().model_dump_json()]
    asyncio.run(RedisMemoryStore("redis://redis").get_context("s"))
    client.expire.assert_awaited_once_with(build_memory_key("s"), 86400)
    tx.rpush.assert_not_called()
