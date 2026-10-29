from app.agent.schemas import (
    AgentOutcome,
    ProviderErrorType,
    QueryExecutionResult,
)
from app.agent.state.records import (
    build_audit_record,
    build_memory_entry,
)


def test_audit_record_is_built_from_execution_data():
    result = QueryExecutionResult(
        columns=["municipio", "receita"],
        rows=[
            ["Recife", 100.0],
            ["Olinda", 80.0],
        ],
        row_count=2,
        truncated=False,
    )

    record = build_audit_record(
        request_id="req-1",
        session_id="sessao-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.ANSWERED,
        sql="SELECT municipio, receita FROM tabela",
        query_result=result,
        regenerations=1,
        final_answer="A receita foi...",
    )

    assert record.request_id == "req-1"
    assert record.session_id == "sessao-1"
    assert record.outcome == AgentOutcome.ANSWERED
    assert record.row_count == 2
    assert record.truncated is False
    assert record.regenerations == 1


def test_audit_without_query_result_has_no_execution_metadata():
    record = build_audit_record(
        request_id="req-1",
        question="Pergunta bloqueada",
        outcome=AgentOutcome.INPUT_BLOCKED,
    )

    assert record.row_count is None
    assert record.truncated is None
    assert record.sql is None


def test_audit_preserves_provider_error():
    record = build_audit_record(
        request_id="req-1",
        question="Qual foi a receita?",
        outcome=AgentOutcome.PROVIDER_ERROR,
        provider_error=ProviderErrorType.TIMEOUT,
    )

    assert record.provider_error == ProviderErrorType.TIMEOUT


def test_answered_outcome_builds_memory_entry():
    entry = build_memory_entry(
        question="Qual foi a receita?",
        answer="A receita foi R$ 100.",
        outcome=AgentOutcome.ANSWERED,
    )

    assert entry is not None
    assert entry.question == "Qual foi a receita?"
    assert entry.answer == "A receita foi R$ 100."
    assert entry.outcome == AgentOutcome.ANSWERED


def test_needs_clarification_can_be_stored_in_memory():
    entry = build_memory_entry(
        question="Compare o consumo.",
        answer="Qual município deseja comparar?",
        outcome=AgentOutcome.NEEDS_CLARIFICATION,
    )

    assert entry is not None


def test_provider_error_does_not_build_memory_entry():
    entry = build_memory_entry(
        question="Qual foi a receita?",
        answer="Serviço indisponível.",
        outcome=AgentOutcome.PROVIDER_ERROR,
    )

    assert entry is None


def test_empty_answer_does_not_build_memory_entry():
    entry = build_memory_entry(
        question="Qual foi a receita?",
        answer="   ",
        outcome=AgentOutcome.ANSWERED,
    )

    assert entry is None