import asyncio
from unittest.mock import Mock

import pytest

from app.agent.guardrails.input_guardrail import validate_input
from app.agent.state import request_state
from app.agent.state.cache_key import build_cache_key
from app.agent.schemas import (
    AgentOutcome,
    MemoryEntry,
    PostProcessingResult,
)
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.request_state import MemoryContextStatus, prepare_request_state


class FakeAuditStore:
    async def save(self, record):
        pass


class FakeMemoryStore:
    def __init__(self, entries=None, fail=False):
        self.entries = entries or []
        self.fail = fail

    async def get_context(self, session_id):
        if self.fail:
            raise RuntimeError("memory unavailable")

        return self.entries

    async def append(self, session_id, entry):
        pass


class FakeCacheStore:
    def __init__(self, value=None, fail=False):
        self.value = value
        self.fail = fail
        self.keys = []

    async def get(self, key):
        self.keys.append(key)

        if self.fail:
            raise RuntimeError("cache unavailable")

        return self.value

    async def set(self, key, value, ttl_seconds):
        pass


def _run(**kwargs):
    return asyncio.run(
        prepare_request_state(**kwargs)
    )


def _memory_entry():
    return MemoryEntry(
        question="Qual foi a receita de janeiro?",
        answer="A receita de janeiro foi R$ 100.",
        outcome=AgentOutcome.ANSWERED,
    )


def test_memory_is_loaded_into_context():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        memory_store=FakeMemoryStore(
            [_memory_entry()]
        ),
    )

    state = _run(
        normalized_question="E em fevereiro?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.memory_context is not None
    assert "receita de janeiro" in state.memory_context
    assert state.cache_hit is False
    assert state.memory_status == MemoryContextStatus.LOADED


def test_cache_hit_returns_cached_response():
    cached = PostProcessingResult(
        answer="Resposta em cache.",
        assumptions=[],
    )

    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        cache_store=FakeCacheStore(cached),
        cache_ttl_seconds=300,
    )

    state = _run(
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.cache_hit is True
    assert state.cached_response == cached
    assert state.memory_status == MemoryContextStatus.NOT_REQUESTED


def test_memory_failure_degrades_gracefully():
    cache = FakeCacheStore(PostProcessingResult(answer="não deve ser reutilizada"))
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        cache_store=cache,
        memory_store=FakeMemoryStore(
            fail=True
        ),
    )

    state = _run(
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.memory_context is None
    assert state.cache_hit is False
    assert state.memory_status == MemoryContextStatus.UNAVAILABLE
    assert state.cache_key is None
    assert cache.keys == []


def test_cache_failure_becomes_cache_miss():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        cache_store=FakeCacheStore(
            fail=True
        ),
        cache_ttl_seconds=300,
    )

    state = _run(
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.cache_hit is False
    assert state.cached_response is None


def test_different_memory_generates_different_cache_key():
    first_dependencies = AgentStateDependencies(
        cache_store=FakeCacheStore(),
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        memory_store=FakeMemoryStore(
            [
                MemoryEntry(
                    question="Pergunta anterior",
                    answer="Janeiro.",
                    outcome=AgentOutcome.ANSWERED,
                )
            ]
        ),
    )

    second_dependencies = AgentStateDependencies(
        cache_store=FakeCacheStore(),
        audit_store=FakeAuditStore(),
        data_version="gold-v1",
        memory_store=FakeMemoryStore(
            [
                MemoryEntry(
                    question="Pergunta anterior",
                    answer="Março.",
                    outcome=AgentOutcome.ANSWERED,
                )
            ]
        ),
    )

    first = _run(
        normalized_question="E no mês seguinte?",
        session_id="sessao-1",
        dependencies=first_dependencies,
    )

    second = _run(
        normalized_question="E no mês seguinte?",
        session_id="sessao-1",
        dependencies=second_dependencies,
    )

    assert first.cache_key != second.cache_key


def test_loaded_empty_memory_allows_cache_get():
    cache = FakeCacheStore()
    state = _run(
        normalized_question="E Recife?", session_id="sessao-1",
        dependencies=AgentStateDependencies(
            audit_store=FakeAuditStore(), memory_store=FakeMemoryStore([]),
            cache_store=cache, data_version="gold-v1",
        ),
    )

    assert state.memory_status == MemoryContextStatus.EMPTY
    assert state.memory_context is None
    assert state.cache_hit is False
    assert cache.keys == [state.cache_key]


def test_key_uses_c1_question_and_exact_effective_context(monkeypatch):
    key_spy = Mock(wraps=build_cache_key)
    monkeypatch.setattr(request_state, "build_cache_key", key_spy)
    normalized = validate_input("   E\rRecife?   ").normalized_input
    state = _run(
        normalized_question=normalized, session_id="sessao-1",
        dependencies=AgentStateDependencies(
            audit_store=FakeAuditStore(), memory_store=FakeMemoryStore([_memory_entry()]),
            cache_store=FakeCacheStore(), data_version="gold-v1",
        ),
    )

    key_spy.assert_called_once_with(
        normalized_question=normalized, session_id="sessao-1",
        memory_context=state.memory_context, data_version="gold-v1",
    )


@pytest.mark.parametrize("value", [{"answer": "antigo"}, "JSON cru", 42,
    PostProcessingResult.model_construct(answer="")])
def test_invalid_adapter_value_is_a_miss(value):
    state = _run(
        normalized_question="Receita?", session_id="s1",
        dependencies=AgentStateDependencies(
            audit_store=FakeAuditStore(), cache_store=FakeCacheStore(value), data_version="gold-v1"
        ),
    )

    assert state.cached_response is None
    assert state.cache_hit is False


def test_cache_get_timeout_is_a_miss_and_cancels_the_operation():
    class HangingCache(FakeCacheStore):
        cancelled = False

        async def get(self, key):
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True

    cache = HangingCache()

    async def run():
        return await asyncio.wait_for(prepare_request_state(
            normalized_question="Receita?", session_id="s1",
            dependencies=AgentStateDependencies(
                audit_store=FakeAuditStore(), cache_store=cache,
                data_version="gold-v1", cache_timeout_seconds=0.01,
            ),
        ), timeout=1)

    state = asyncio.run(run())
    assert state.cache_hit is False
    assert cache.cancelled is True


def test_cache_disabled_does_not_require_version_or_produce_key():
    state = _run(
        normalized_question="Receita?", session_id="s1",
        dependencies=AgentStateDependencies(audit_store=FakeAuditStore()),
    )

    assert state.cache_key is None
    assert state.cache_hit is False


def test_concurrent_requests_keep_session_and_context_isolated():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.agent.state.memory_context import build_memory_context
    entries = {
        session: [MemoryEntry(question="Contexto anterior.", answer=f"Resposta {session}.", outcome=AgentOutcome.ANSWERED)]
        for session in ("s1", "s2")
    }
    question = "E no mês anterior?"
    expected = {
        build_cache_key(normalized_question=question, session_id=session,
                        memory_context=build_memory_context(history), data_version="gold-v1"):
        PostProcessingResult(answer=f"Cache {session}.")
        for session, history in entries.items()
    }
    async def get_context(session):
        await asyncio.sleep(0)
        return list(entries[session])
    async def get_cache(key):
        await asyncio.sleep(0)
        return expected[key]
    dependencies = AgentStateDependencies(
        cache_store=SimpleNamespace(get=AsyncMock(side_effect=get_cache), set=AsyncMock()),
        memory_store=SimpleNamespace(get_context=get_context), data_version="gold-v1",
    )
    async def run():
        return await asyncio.gather(*[
            prepare_request_state(normalized_question=question, session_id=session, dependencies=dependencies)
            for session in ("s1", "s2")
        ])
    states = asyncio.run(run())
    for session, state in zip(("s1", "s2"), states):
        assert state.cache_hit
        assert state.cached_response.answer == f"Cache {session}."
        assert state.memory_context == build_memory_context(entries[session])
    assert states[0].cache_key != states[1].cache_key
    dependencies.cache_store.set.assert_not_awaited()
