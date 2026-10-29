import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    QueryExecutionResult,
    SQLExecutionErrorType,
    SQLExecutionOutcome,
    SQLExecutionStatus,
)


def _result():
    return QueryExecutionResult(
        columns=["a"], rows=[[1]], row_count=1
    )


def test_success_requires_a_result():
    with pytest.raises(ValidationError):
        SQLExecutionOutcome(status=SQLExecutionStatus.SUCCESS)


def test_success_cannot_have_an_error_type():
    with pytest.raises(ValidationError):
        SQLExecutionOutcome(
            status=SQLExecutionStatus.SUCCESS,
            result=_result(),
            error_type=SQLExecutionErrorType.TIMEOUT,
        )


def test_failure_requires_an_error_type():
    with pytest.raises(ValidationError):
        SQLExecutionOutcome(status=SQLExecutionStatus.FAILED)


def test_failure_cannot_have_a_result():
    with pytest.raises(ValidationError):
        SQLExecutionOutcome(
            status=SQLExecutionStatus.FAILED,
            result=_result(),
            error_type=SQLExecutionErrorType.TIMEOUT,
        )


def test_valid_success_and_failure():
    success = SQLExecutionOutcome(
        status=SQLExecutionStatus.SUCCESS, result=_result()
    )
    failure = SQLExecutionOutcome(
        status=SQLExecutionStatus.FAILED,
        error_type=SQLExecutionErrorType.TABLE_NOT_FOUND,
        error_detail="no such table: x",
    )

    assert success.result.row_count == 1
    assert failure.error_type == SQLExecutionErrorType.TABLE_NOT_FOUND