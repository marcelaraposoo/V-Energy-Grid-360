from __future__ import annotations

from app.agent.post_processor import post_process
from app.agent.schemas import (
    PostProcessingResult,
    QueryExecutionResult,
)
from app.agent.synthesis_orchestrator import SynthesisFlowResult


def process_approved_response(
    flow: SynthesisFlowResult,
    result: QueryExecutionResult,
) -> PostProcessingResult | None:

    if not flow.approved:
        return None

    if flow.synthesis is None:
        return None

    return post_process(
        synthesis=flow.synthesis,
        result=result,
    )