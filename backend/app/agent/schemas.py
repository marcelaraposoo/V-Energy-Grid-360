from enum import Enum

from pydantic import BaseModel


class GuardrailDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class GuardrailReason(str, Enum):
    INVALID_INPUT = "invalid_input"
    INPUT_TOO_LONG = "input_too_long"
    DIRECT_SQL = "direct_sql"
    URL_NOT_SUPPORTED = "url_not_supported"
    PROMPT_INJECTION_PATTERN = "prompt_injection_pattern"
    GUARDRAIL_INTERNAL_ERROR = "guardrail_internal_error"


class InputGuardrailResult(BaseModel):
    decision: GuardrailDecision
    reason: GuardrailReason | None = None

    original_input: str
    normalized_input: str | None = None