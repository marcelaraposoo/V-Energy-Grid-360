import asyncio
from datetime import datetime, timezone

from app.agent import sql_execution_orchestrator as orchestrator
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    ProviderName,
    QueryExecutionResult,
    SQLExecutionErrorType,
    SQLExecutionOutcome,
    SQLExecutionStatus,
    SQLGenerationResult,
    SQLGenerationStatus,
    SQLGuardrailReason,
)


GOOD_SQL = "SELECT COUNT(*) FROM dim_uc"
OTHER_GOOD_SQL = "SELECT classe FROM dim_uc"
BAD_SQL = "DELETE FROM dim_uc"


def _ready(sql):
    return SQLGenerationResult(
        status=SQLGenerationStatus.READY, sql=sql
    )


def _attempt():
    return ProviderAttempt(
        provider=ProviderName.GEMINI,
        model="modelo-teste",
        attempt=1,
        started_at=datetime.now(timezone.utc),
        success=True,
    )


def _success():
    return SQLExecutionOutcome(
        status=SQLExecutionStatus.SUCCESS,
        result=QueryExecutionResult(
            columns=["n"], rows=[[1]], row_count=1
        ),
    )


def _failure(error_type, detail=""):
    return SQLExecutionOutcome(
        status=SQLExecutionStatus.FAILED,
        error_type=error_type,
        error_detail=detail,
    )


def _install(monkeypatch, generations, outcomes):
    """generations: lista de (SQLGenerationResult|None, erro de provider).
    outcomes: lista de SQLExecutionOutcome devolvidos em ordem."""
    feedbacks = []
    executed = []

    async def fake_generate_sql(
        question,
        database_context,
        memory_context=None,
        guardrail_feedback=None,
    ):
        feedbacks.append(guardrail_feedback)
        generation, error = generations[len(feedbacks) - 1]

        return generation, [_attempt()], error

    def fake_execute_sql(sql, **kwargs):
        executed.append(sql)

        return outcomes[len(executed) - 1]

    monkeypatch.setattr(orchestrator, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(orchestrator, "execute_sql", fake_execute_sql)

    return feedbacks, executed


def _run():
    return asyncio.run(
        orchestrator.generate_validate_and_execute(
            "Quantas UCs?", "contexto"
        )
    )


def test_max_regenerations_is_one():
    assert orchestrator.MAX_REGENERATIONS == 1


def test_successful_flow_executes_once(monkeypatch):
    feedbacks, executed = _install(
        monkeypatch, [(_ready(GOOD_SQL), None)], [_success()]
    )

    flow = _run()

    assert flow.executed is True
    assert flow.sql == GOOD_SQL
    assert flow.regenerations == 0
    assert executed == [GOOD_SQL]
    assert feedbacks == [None]


def test_non_ready_generation_is_not_executed(monkeypatch):
    generation = SQLGenerationResult(
        status=SQLGenerationStatus.OUT_OF_SCOPE,
        reason="Fora do domínio.",
    )
    _, executed = _install(monkeypatch, [(generation, None)], [])

    flow = _run()

    assert flow.executed is False
    assert flow.generation_status == SQLGenerationStatus.OUT_OF_SCOPE
    assert executed == []


def test_provider_error_stops_the_flow(monkeypatch):
    _, executed = _install(
        monkeypatch, [(None, ProviderErrorType.RATE_LIMITED)], []
    )

    flow = _run()

    assert flow.provider_error == ProviderErrorType.RATE_LIMITED
    assert executed == []


def test_blocked_sql_is_never_executed(monkeypatch):
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(BAD_SQL), None), (_ready(BAD_SQL), None)],
        [],
    )

    flow = _run()

    assert flow.executed is False
    assert flow.guardrail_reason == SQLGuardrailReason.FORBIDDEN_OPERATION
    assert executed == []
    assert flow.regenerations == 1
    assert len(feedbacks) == 2


def test_blocked_sql_is_regenerated_once_and_then_executed(monkeypatch):
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(BAD_SQL), None), (_ready(GOOD_SQL), None)],
        [_success()],
    )

    flow = _run()

    assert flow.executed is True
    assert flow.regenerations == 1
    assert executed == [GOOD_SQL]
    assert feedbacks[0] is None
    assert BAD_SQL in feedbacks[1]


def test_missing_column_is_regenerated_once(monkeypatch):
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(GOOD_SQL), None), (_ready(OTHER_GOOD_SQL), None)],
        [
            _failure(
                SQLExecutionErrorType.COLUMN_NOT_FOUND,
                "OperationalError: no such column: coluna_fantasma",
            ),
            _success(),
        ],
    )

    flow = _run()

    assert flow.executed is True
    assert flow.regenerations == 1
    assert executed == [GOOD_SQL, OTHER_GOOD_SQL]
    assert "coluna_fantasma" in feedbacks[1]
    assert "OperationalError" not in feedbacks[1]


def test_missing_table_is_regenerated_once(monkeypatch):
    feedbacks, _ = _install(
        monkeypatch,
        [(_ready(GOOD_SQL), None), (_ready(OTHER_GOOD_SQL), None)],
        [
            _failure(
                SQLExecutionErrorType.TABLE_NOT_FOUND,
                "OperationalError: no such table: tabela_fantasma",
            ),
            _success(),
        ],
    )

    flow = _run()

    assert flow.executed is True
    assert "tabela_fantasma" in feedbacks[1]


def test_second_execution_error_is_returned_without_a_third_try(
    monkeypatch,
):
    error = _failure(
        SQLExecutionErrorType.COLUMN_NOT_FOUND,
        "no such column: x",
    )
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(GOOD_SQL), None), (_ready(OTHER_GOOD_SQL), None)],
        [error, error],
    )

    flow = _run()

    assert flow.executed is False
    assert flow.outcome.error_type == SQLExecutionErrorType.COLUMN_NOT_FOUND
    assert flow.regenerations == 1
    assert len(feedbacks) == 2
    assert len(executed) == 2


def test_timeout_is_not_regenerated(monkeypatch):
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(GOOD_SQL), None)],
        [_failure(SQLExecutionErrorType.TIMEOUT, "interrupted")],
    )

    flow = _run()

    assert flow.executed is False
    assert flow.outcome.error_type == SQLExecutionErrorType.TIMEOUT
    assert flow.regenerations == 0
    assert len(feedbacks) == 1


def test_regeneration_budget_is_shared_with_the_guardrail(monkeypatch):
    """Se a 4.2 já usou a regeneração, a 4.3 não regenera."""
    feedbacks, executed = _install(
        monkeypatch,
        [(_ready(BAD_SQL), None), (_ready(GOOD_SQL), None)],
        [
            _failure(
                SQLExecutionErrorType.COLUMN_NOT_FOUND,
                "no such column: x",
            )
        ],
    )

    flow = _run()

    assert flow.executed is False
    assert flow.outcome.error_type == SQLExecutionErrorType.COLUMN_NOT_FOUND
    assert flow.regenerations == 1
    assert len(feedbacks) == 2
    assert executed == [GOOD_SQL]


def test_execution_feedback_without_object_name_is_still_generated():
    outcome = _failure(
        SQLExecutionErrorType.COLUMN_NOT_FOUND, "erro sem nome"
    )

    feedback = orchestrator.build_execution_retry_feedback(
        GOOD_SQL, outcome
    )

    assert feedback is not None
    assert GOOD_SQL in feedback


def test_execution_feedback_is_not_built_for_other_errors():
    outcome = _failure(SQLExecutionErrorType.TIMEOUT, "interrupted")

    assert (
        orchestrator.build_execution_retry_feedback(GOOD_SQL, outcome)
        is None
    )