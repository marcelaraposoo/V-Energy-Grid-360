import asyncio

from app.agent.schemas import (
    AgentOutcome,
    MemoryEntry,
    PostProcessingResult,
)
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.request_state import prepare_request_state


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
        memory_store=FakeMemoryStore(
            [_memory_entry()]
        ),
    )

    state = _run(
        question="E em fevereiro?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.memory_context is not None
    assert "receita de janeiro" in state.memory_context
    assert state.cache_hit is False


def test_cache_hit_returns_cached_response():
    cached = PostProcessingResult(
        answer="Resposta em cache.",
        assumptions=[],
    )

    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        cache_store=FakeCacheStore(cached),
        cache_ttl_seconds=300,
    )

    state = _run(
        question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.cache_hit is True
    assert state.cached_response == cached


def test_memory_failure_degrades_gracefully():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        memory_store=FakeMemoryStore(
            fail=True
        ),
    )

    state = _run(
        question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.memory_context is None
    assert state.cache_hit is False


def test_cache_failure_becomes_cache_miss():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        cache_store=FakeCacheStore(
            fail=True
        ),
        cache_ttl_seconds=300,
    )

    state = _run(
        question="Qual foi a receita?",
        session_id="sessao-1",
        dependencies=dependencies,
    )

    assert state.cache_hit is False
    assert state.cached_response is None


def test_different_memory_generates_different_cache_key():
    first_dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
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
        audit_store=FakeAuditStore(),
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
        question="E no mês seguinte?",
        session_id="sessao-1",
        dependencies=first_dependencies,
    )

    second = _run(
        question="E no mês seguinte?",
        session_id="sessao-1",
        dependencies=second_dependencies,
    )

    assert first.cache_key != second.cache_key