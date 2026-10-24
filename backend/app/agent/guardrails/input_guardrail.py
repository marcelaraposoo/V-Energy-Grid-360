from app.agent.schemas import (
    GuardrailDecision,
    GuardrailReason,
    InputGuardrailResult,
)

from app.agent.guardrails.rules import (
    normalize_input,
    lacks_useful_content,
    exceeds_max_length,
    contains_direct_sql,
    contains_url,
    matches_prompt_injection_pattern,
)


VALIDATION_RULES = (
    (
        lacks_useful_content,
        GuardrailReason.INVALID_INPUT,
    ),
    (
        exceeds_max_length,
        GuardrailReason.INPUT_TOO_LONG,
    ),
    (
        contains_direct_sql,
        GuardrailReason.DIRECT_SQL,
    ),
    (
        contains_url,
        GuardrailReason.URL_NOT_SUPPORTED,
    ),
    (
        matches_prompt_injection_pattern,
        GuardrailReason.PROMPT_INJECTION_PATTERN,
    ),
)


def validate_input(message: str) -> InputGuardrailResult:
    original_input = message

    try:
        normalized_input = normalize_input(message)

        for rule, reason in VALIDATION_RULES:
            if rule(normalized_input):
                return InputGuardrailResult(
                    decision=GuardrailDecision.BLOCK,
                    reason=reason,
                    original_input=original_input,
                    normalized_input=normalized_input,
                )

        return InputGuardrailResult(
            decision=GuardrailDecision.ALLOW,
            reason=None,
            original_input=original_input,
            normalized_input=normalized_input,
        )

    except Exception:
        return InputGuardrailResult(
            decision=GuardrailDecision.BLOCK,
            reason=GuardrailReason.GUARDRAIL_INTERNAL_ERROR,
            original_input=original_input,
            normalized_input=None,
        )