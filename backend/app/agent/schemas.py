from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


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

# =========================================================
# GUARDRAIL DE SQL — ETAPA 4.2
# =========================================================
class SQLGuardrailDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class SQLGuardrailReason(str, Enum):
    INVALID_SQL = "invalid_sql"
    MULTIPLE_STATEMENTS = "multiple_statements"
    FORBIDDEN_OPERATION = "forbidden_operation"
    UNSUPPORTED_QUERY = "unsupported_query"
    GUARDRAIL_INTERNAL_ERROR = "guardrail_internal_error"


class SQLGuardrailResult(BaseModel):
    decision: SQLGuardrailDecision
    reason: SQLGuardrailReason | None = None
    retryable: bool = False
    original_sql: str

# =========================================================
# EXECUÇÃO SQL — ETAPA 4.3 (contrato provisório)
# =========================================================
class QueryExecutionResult(BaseModel):
    """
    Resultado da execução do SQL produzido pela camada 4.3.
    Contrato provisório, mudar se a 4.3 definir outro formato.
    """

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False

    @model_validator(mode="after")
    def validate_result(self):
        if self.row_count < 0:
            raise ValueError(
                "row_count não pode ser negativo."
            )

        if len(self.rows) > self.row_count:
            raise ValueError(
                "rows não pode ter mais linhas que row_count."
            )

        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    "Toda linha deve ter o mesmo número "
                    "de valores que columns."
                )

        return self


# =========================================================
# SÍNTESE DA RESPOSTA — ETAPA 4.4
# =========================================================


class SynthesisStatus(str, Enum):
    ANSWERED = "answered"
    NO_DATA = "no_data"


class SynthesisResult(BaseModel):
    status: SynthesisStatus
    answer: str
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self):
        if not self.answer or not self.answer.strip():
            raise ValueError(
                "answer é obrigatório."
            )

        return self