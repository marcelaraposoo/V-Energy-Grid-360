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

        if not self.truncated and len(self.rows) != self.row_count:
            raise ValueError(
                "Sem truncamento, row_count deve ser igual "
                "ao número de linhas em rows."
            )

        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    "Toda linha deve ter o mesmo número "
                    "de valores que columns."
                )

        return self

# =========================================================
# EXECUÇÃO SQL — ETAPA 4.3
# =========================================================


class SQLExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class SQLExecutionErrorType(str, Enum):
    TABLE_NOT_FOUND = "table_not_found"
    COLUMN_NOT_FOUND = "column_not_found"
    TIMEOUT = "timeout"
    DATABASE_UNAVAILABLE = "database_unavailable"
    EXECUTION_ERROR = "execution_error"


class SQLExecutionOutcome(BaseModel):
    """
    Resultado da execução do SQL.

    O texto original do erro do banco fica em `error_detail`,
    só para log técnico. Ele nunca vai ao usuário.
    """

    status: SQLExecutionStatus
    result: QueryExecutionResult | None = None
    error_type: SQLExecutionErrorType | None = None
    error_detail: str | None = None
    elapsed_ms: float = 0.0

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.status == SQLExecutionStatus.SUCCESS:
            if self.result is None:
                raise ValueError(
                    "result é obrigatório quando o status é SUCCESS."
                )

            if self.error_type is not None:
                raise ValueError(
                    "error_type deve ser None quando o status é SUCCESS."
                )

            return self

        if self.result is not None:
            raise ValueError(
                "result deve ser None quando o status é FAILED."
            )

        if self.error_type is None:
            raise ValueError(
                "error_type é obrigatório quando o status é FAILED."
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

# =========================================================
# GUARDRAIL DE SAÍDA — CAMADA 5
# =========================================================


class OutputGuardrailDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


class OutputGuardrailReason(str, Enum):
    EMPTY_ANSWER = "empty_answer"
    ANSWER_TOO_LONG = "answer_too_long"
    UNSUPPORTED_NUMBER = "unsupported_number"
    URL_IN_ANSWER = "url_in_answer"
    SQL_IN_ANSWER = "sql_in_answer"
    PROMPT_LEAK = "prompt_leak"
    PROVIDER_DISCLOSURE = "provider_disclosure"
    TECHNICAL_ERROR_LEAK = "technical_error_leak"
    GUARDRAIL_INTERNAL_ERROR = "guardrail_internal_error"


class OutputGuardrailResult(BaseModel):
    decision: OutputGuardrailDecision
    reason: OutputGuardrailReason | None = None
    retryable: bool = False
    original_answer: str
    unsupported_values: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self):
        if self.decision == OutputGuardrailDecision.ALLOW:
            if (
                self.reason is not None
                or self.retryable
                or self.unsupported_values
            ):
                raise ValueError(
                    "ALLOW não pode ter reason, retryable "
                    "nem unsupported_values."
                )

            return self

        if self.reason is None:
            raise ValueError(
                "reason é obrigatório quando a decisão é BLOCK."
            )

        if (
            self.unsupported_values
            and self.reason
            != OutputGuardrailReason.UNSUPPORTED_NUMBER
        ):
            raise ValueError(
                "unsupported_values só é válido com "
                "UNSUPPORTED_NUMBER."
            )

        return self

# =========================================================
# PÓS-PROCESSAMENTO — CAMADA 6
# =========================================================


class VisualizationType(str, Enum):
    LINE = "line"
    BAR = "bar"


class VisualizationPoint(BaseModel):
    """
    Um ponto utilizado pelo frontend para renderizar
    uma visualização analítica.
    """

    label: str
    value: float


class VisualizationSpec(BaseModel):
    """
    Especificação de visualização produzida pela Camada 6.

    O backend não renderiza o gráfico. Ele apenas informa
    ao frontend qual visualização pode ser construída e
    quais dados devem ser utilizados.
    """

    type: VisualizationType
    title: str

    x_label: str | None = None
    y_label: str | None = None
    unit: str | None = None

    points: list[VisualizationPoint]

    @model_validator(mode="after")
    def validate_visualization(self):
        if not self.title or not self.title.strip():
            raise ValueError(
                "title é obrigatório para uma visualização."
            )

        if not self.points:
            raise ValueError(
                "Uma visualização precisa possuir ao menos um ponto."
            )

        return self


class PostProcessingResult(BaseModel):
    """
    Resultado final da Camada 6.

    `answer` e `assumptions` vêm da síntese já aprovada
    pelo Output Guardrail.

    `visualization` é opcional e é construída exclusivamente
    a partir do QueryExecutionResult.
    """

    answer: str
    assumptions: list[str] = Field(default_factory=list)
    visualization: VisualizationSpec | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if not self.answer or not self.answer.strip():
            raise ValueError(
                "answer é obrigatório."
            )

        return self