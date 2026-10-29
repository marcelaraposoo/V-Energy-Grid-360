import asyncio

from app.agent.schemas import (
    AgentOutcome,
    PostProcessingResult,
    ProviderErrorType,
    QueryExecutionResult,
)
from app.agent.state.service import finalize_request


class FakeAuditStore:
    def __init__(self):
        self.records = []

    async def save(self, record):
        self.records.append(record)


class FakeMemoryStore:
    def __init__(self):
        self.entries = []

    async def get_context(self, session_id):
        return []

    async def append(self, session_id, entry):
        self.entries.append((session_id, entry))


class FakeCacheStore:
    def __init__(self):
        self.values = []

    async def get(self, key):
        return None

    async def set(self, key, value, ttl_seconds):
        self.values.append(
            (key, value, ttl_seconds)
        )


def _run(**kwargs):
    asyncio.run(
        finalize_request(**kwargs)
    )


def test_answered_request_finalizes_all_eligible_state():
    audit = FakeAuditStore()
    memory = FakeMemoryStore()
    cache = FakeCacheStore()

    query_result = QueryExecutionResult(
        columns=["receita"],
        rows=[[100.0]],
        row_count=1,
        truncated=False,
    )

    cache_value = PostProcessingResult(
        answer="A receita foi R$ 100.",
        assumptions=[],
    )

    _run(
        audit_store=audit,
        memory_store=memory,
        cache_store=cache,
        request_id="req-1",
        session_id="sessao-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.ANSWERED,
        final_answer="A receita foi R$ 100.",
        sql="SELECT receita FROM tabela",
        query_result=query_result,
        cache_key="cache-key",
        cache_value=cache_value,
        cache_ttl_seconds=300,
    )

    assert len(audit.records) == 1
    assert len(memory.entries) == 1
    assert len(cache.values) == 1

    record = audit.records[0]

    assert record.outcome == AgentOutcome.ANSWERED
    assert record.row_count == 1
    assert record.final_answer == "A receita foi R$ 100."


def test_provider_error_is_only_audited():
    audit = FakeAuditStore()
    memory = FakeMemoryStore()
    cache = FakeCacheStore()

    _run(
        audit_store=audit,
        memory_store=memory,
        cache_store=cache,
        request_id="req-2",
        session_id="sessao-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.PROVIDER_ERROR,
        final_answer="Serviço indisponível.",
        provider_error=ProviderErrorType.TIMEOUT,
        cache_key="cache-key",
        cache_value=PostProcessingResult(
            answer="Serviço indisponível.",
            assumptions=[],
        ),
        cache_ttl_seconds=300,
    )

    assert len(audit.records) == 1
    assert memory.entries == []
    assert cache.values == []

    assert (
        audit.records[0].provider_error
        == ProviderErrorType.TIMEOUT
    )


def test_cache_hit_is_audited_and_not_rewritten():
    audit = FakeAuditStore()
    memory = FakeMemoryStore()
    cache = FakeCacheStore()

    _run(
        audit_store=audit,
        memory_store=memory,
        cache_store=cache,
        request_id="req-3",
        session_id="sessao-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.ANSWERED,
        final_answer="A receita foi R$ 100.",
        cache_hit=True,
        cache_key="cache-key",
        cache_value=PostProcessingResult(
            answer="A receita foi R$ 100.",
            assumptions=[],
        ),
        cache_ttl_seconds=300,
    )

    assert len(audit.records) == 1
    assert audit.records[0].cache_hit is True

    assert len(memory.entries) == 1
    assert cache.values == []