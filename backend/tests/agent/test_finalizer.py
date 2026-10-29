import asyncio

from app.agent.schemas import (
    AgentOutcome,
    AuditRecord,
    MemoryEntry,
    PostProcessingResult,
)
from app.agent.state.finalizer import finalize


class FakeAuditStore:
    def __init__(self, fail: bool = False):
        self.records = []
        self.fail = fail

    async def save(self, record):
        if self.fail:
            raise RuntimeError("audit failure")

        self.records.append(record)


class FakeMemoryStore:
    def __init__(self, fail: bool = False):
        self.entries = []
        self.fail = fail

    async def get_context(self, session_id):
        return []

    async def append(self, session_id, entry):
        if self.fail:
            raise RuntimeError("memory failure")

        self.entries.append((session_id, entry))


class FakeCacheStore:
    def __init__(self, fail: bool = False):
        self.values = []
        self.fail = fail

    async def get(self, key):
        return None

    async def set(self, key, value, ttl_seconds):
        if self.fail:
            raise RuntimeError("cache failure")

        self.values.append((key, value, ttl_seconds))


def _audit(
    outcome=AgentOutcome.ANSWERED,
    *,
    session_id="sessao-1",
    cache_hit=False,
):
    return AuditRecord(
        request_id="req-1",
        session_id=session_id,
        question="Qual foi a receita?",
        outcome=outcome,
        cache_hit=cache_hit,
        final_answer="A receita foi de R$ 100.",
    )


def _memory_entry(
    outcome=AgentOutcome.ANSWERED,
):
    return MemoryEntry(
        question="Qual foi a receita?",
        answer="A receita foi de R$ 100.",
        outcome=outcome,
    )


def _cache_value():
    return PostProcessingResult(
        answer="A receita foi de R$ 100.",
        assumptions=[],
    )


def _run(**kwargs):
    return asyncio.run(finalize(**kwargs))


def test_audit_is_always_saved():
    audit_store = FakeAuditStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(),
    )

    assert len(audit_store.records) == 1


def test_eligible_outcome_is_stored_in_memory():
    audit_store = FakeAuditStore()
    memory_store = FakeMemoryStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(),
        memory_store=memory_store,
        memory_entry=_memory_entry(),
    )

    assert len(memory_store.entries) == 1
    assert memory_store.entries[0][0] == "sessao-1"


def test_memory_is_not_stored_without_session():
    audit_store = FakeAuditStore()
    memory_store = FakeMemoryStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(session_id=None),
        memory_store=memory_store,
        memory_entry=_memory_entry(),
    )

    assert memory_store.entries == []


def test_ineligible_outcome_is_not_stored_in_memory():
    audit_store = FakeAuditStore()
    memory_store = FakeMemoryStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(
            outcome=AgentOutcome.PROVIDER_ERROR,
        ),
        memory_store=memory_store,
        memory_entry=_memory_entry(
            outcome=AgentOutcome.PROVIDER_ERROR,
        ),
    )

    assert memory_store.entries == []


def test_answered_response_is_stored_in_cache():
    audit_store = FakeAuditStore()
    cache_store = FakeCacheStore()
    value = _cache_value()

    _run(
        audit_store=audit_store,
        audit_record=_audit(),
        cache_store=cache_store,
        cache_key="cache-key",
        cache_value=value,
        cache_ttl_seconds=300,
    )

    assert cache_store.values == [
        ("cache-key", value, 300)
    ]


def test_cache_hit_is_not_written_again():
    audit_store = FakeAuditStore()
    cache_store = FakeCacheStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(cache_hit=True),
        cache_store=cache_store,
        cache_key="cache-key",
        cache_value=_cache_value(),
        cache_ttl_seconds=300,
    )

    assert cache_store.values == []


def test_ineligible_outcome_is_not_cached():
    audit_store = FakeAuditStore()
    cache_store = FakeCacheStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(
            outcome=AgentOutcome.NO_DATA,
        ),
        cache_store=cache_store,
        cache_key="cache-key",
        cache_value=_cache_value(),
        cache_ttl_seconds=300,
    )

    assert cache_store.values == []


def test_invalid_ttl_does_not_write_cache():
    audit_store = FakeAuditStore()
    cache_store = FakeCacheStore()

    _run(
        audit_store=audit_store,
        audit_record=_audit(),
        cache_store=cache_store,
        cache_key="cache-key",
        cache_value=_cache_value(),
        cache_ttl_seconds=0,
    )

    assert cache_store.values == []


def test_store_failures_do_not_break_finalization():
    audit_store = FakeAuditStore(fail=True)
    memory_store = FakeMemoryStore(fail=True)
    cache_store = FakeCacheStore(fail=True)

    _run(
        audit_store=audit_store,
        audit_record=_audit(),
        memory_store=memory_store,
        memory_entry=_memory_entry(),
        cache_store=cache_store,
        cache_key="cache-key",
        cache_value=_cache_value(),
        cache_ttl_seconds=300,
    )