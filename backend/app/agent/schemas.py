from datetime import datetime
from enum import Enum

from pydantic import BaseModel


# =========================================================
# GUARDRAIL
# =========================================================


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


# =========================================================
# PROVIDERS
# =========================================================


class ProviderName(str, Enum):
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class ProviderErrorType(str, Enum):
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"

    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"

    CONFIGURATION_ERROR = "configuration_error"
    INVALID_OUTPUT = "invalid_output"

    UNKNOWN = "unknown"


class ProviderAttempt(BaseModel):
    provider: ProviderName
    model: str
    attempt: int
    started_at: datetime

    success: bool
    latency_ms: float | None = None
    error_type: ProviderErrorType | None = None
