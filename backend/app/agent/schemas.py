from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


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

# =========================================================
# GERAÇÃO DE SQL — ETAPA 4.1
# =========================================================


class SQLGenerationStatus(str, Enum):
    READY = "ready"
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    REJECTED = "rejected"


class SQLGenerationResult(BaseModel):
    status: SQLGenerationStatus
    sql: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if self.status == SQLGenerationStatus.READY:
            if not self.sql or not self.sql.strip():
                raise ValueError(
                    "sql é obrigatório quando o status é READY."
                )

            return self

        if self.sql is not None:
            raise ValueError(
                "sql deve ser None quando o status não é READY."
            )

        if not self.reason or not self.reason.strip():
            raise ValueError(
                "reason é obrigatório quando o status não é READY."
            )

        return self