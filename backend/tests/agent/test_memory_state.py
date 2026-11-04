from app.agent.schemas import AgentOutcome
from app.agent.state.memory import should_store_in_memory


def test_answered_is_stored_in_memory():
    assert should_store_in_memory(AgentOutcome.ANSWERED)


def test_no_data_is_stored_in_memory():
    assert should_store_in_memory(AgentOutcome.NO_DATA)


def test_needs_clarification_is_stored_in_memory():
    assert should_store_in_memory(
        AgentOutcome.NEEDS_CLARIFICATION
    )


def test_provider_error_is_not_stored_in_memory():
    assert not should_store_in_memory(
        AgentOutcome.PROVIDER_ERROR
    )


def test_input_blocked_is_not_stored_in_memory():
    assert not should_store_in_memory(
        AgentOutcome.INPUT_BLOCKED
    )


def test_output_blocked_is_not_stored_in_memory():
    assert not should_store_in_memory(
        AgentOutcome.OUTPUT_BLOCKED
    )