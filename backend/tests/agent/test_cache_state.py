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