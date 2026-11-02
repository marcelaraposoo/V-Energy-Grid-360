from datetime import timezone

from app.agent.schemas import (
    AgentOutcome,
    AuditRecord,
    ProviderErrorType,
)


def test_audit_record_minimal():
    record = AuditRecord(
        request_id="req-123",
        question="Qual foi o consumo?",
        outcome=AgentOutcome.ANSWERED,
    )

    assert record.request_id == "req-123"
    assert record.session_id is None
    assert record.question == "Qual foi o consumo?"
    assert record.outcome == AgentOutcome.ANSWERED

    assert record.cache_hit is False
    assert record.sql is None
    assert record.row_count is None
    assert record.truncated is None
    assert record.provider_error is None
    assert record.regenerations == 0
    assert record.final_answer is None

    assert record.timestamp.tzinfo == timezone.utc


def test_audit_record_answered():
    record = AuditRecord(
        request_id="req-answered",
        session_id="session-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.ANSWERED,
        sql="SELECT SUM(valor_total) FROM fato_consumo_faturamento",
        row_count=1,
        truncated=False,
        regenerations=1,
        final_answer="A receita total foi...",
    )

    assert record.session_id == "session-1"
    assert record.sql is not None
    assert record.row_count == 1
    assert record.truncated is False
    assert record.regenerations == 1
    assert record.final_answer == "A receita total foi..."


def test_audit_record_cache_hit():
    record = AuditRecord(
        request_id="req-cache",
        session_id="session-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.ANSWERED,
        cache_hit=True,
        final_answer="Resposta recuperada do cache.",
    )

    assert record.outcome == AgentOutcome.ANSWERED
    assert record.cache_hit is True


def test_audit_record_provider_error():
    record = AuditRecord(
        request_id="req-error",
        question="Qual foi o consumo?",
        outcome=AgentOutcome.PROVIDER_ERROR,
        provider_error=ProviderErrorType.PROVIDER_UNAVAILABLE,
    )

    assert record.outcome == AgentOutcome.PROVIDER_ERROR
    assert (
        record.provider_error
        == ProviderErrorType.PROVIDER_UNAVAILABLE
    )


def test_audit_record_blocked_without_sql_or_answer():
    record = AuditRecord(
        request_id="req-blocked",
        question="DELETE FROM usuarios",
        outcome=AgentOutcome.INPUT_BLOCKED,
    )

    assert record.outcome == AgentOutcome.INPUT_BLOCKED
    assert record.sql is None
    assert record.final_answer is None