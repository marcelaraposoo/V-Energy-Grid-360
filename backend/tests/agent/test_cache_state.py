import pytest

from app.agent.schemas import AgentOutcome
from app.agent.state.cache import should_store_in_cache


def test_answered_is_cacheable():
    assert should_store_in_cache(
        AgentOutcome.ANSWERED
    )


def test_no_data_is_not_cacheable():
    assert not should_store_in_cache(
        AgentOutcome.NO_DATA
    )


def test_needs_clarification_is_not_cacheable():
    assert not should_store_in_cache(
        AgentOutcome.NEEDS_CLARIFICATION
    )


def test_provider_error_is_not_cacheable():
    assert not should_store_in_cache(
        AgentOutcome.PROVIDER_ERROR
    )


def test_output_blocked_is_not_cacheable():
    assert not should_store_in_cache(
        AgentOutcome.OUTPUT_BLOCKED
    )
@pytest.mark.parametrize("outcome", list(AgentOutcome))
def test_only_answered_is_cacheable(outcome):
    assert should_store_in_cache(outcome) == (outcome == AgentOutcome.ANSWERED)


@pytest.mark.parametrize("truncated", [True, None])
def test_truncated_or_unknown_execution_is_not_cacheable(truncated):
    assert not should_store_in_cache(AgentOutcome.ANSWERED, truncated=truncated)


def test_incomplete_response_is_not_cacheable():
    assert not should_store_in_cache(AgentOutcome.ANSWERED, response_complete=False)
