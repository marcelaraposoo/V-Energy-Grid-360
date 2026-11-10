from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
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


class ProviderPhase(str, Enum):
    SQL_GENERATION = "sql_generation"
    SYNTHESIS = "synthesis"


class ProviderAttempt(BaseModel):
    phase: ProviderPhase | None = None
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
    KNOWLEDGE = "knowledge"
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    REJECTED = "rejected"


class GeographicReference(BaseModel):
    kind: Literal["municipio", "bairro"]
    name: str = Field(min_length=1, max_length=100)


class RequestedPeriod(BaseModel):
    granularity: Literal["year", "month", "range", "all", "latest"]
    start: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    reference: Literal["explicit", "calendar", "conversation", "coverage"]

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.granularity in {"year", "month", "range"}:
            if not self.start or not self.end or self.start > self.end:
                raise ValueError("Período solicitado exige limites ordenados.")
            if self.granularity == "year":
                if self.start[:4] != self.end[:4]:
                    raise ValueError("Um ano solicitado precisa ter o mesmo ano nos limites.")
                # Ano significa calendário completo, independentemente de cobertura.
                self.start, self.end = self.start[:4] + "-01", self.end[:4] + "-12"
            if self.granularity == "month" and self.start != self.end:
                raise ValueError("Um mês exige limites iguais.")
        return self


class SemanticIntent(BaseModel):
    """Interpretação proposta pelo modelo; não concede autorização de execução."""
    requested_outputs: list[str] = Field(default_factory=list, max_length=6,
        description="Cada entrega solicitada, antes de escolher a rota: explicações, valores, comparações.")
    ambiguities: list[str] = Field(default_factory=list, max_length=4,
        description="Significados indispensáveis ainda indefinidos; gasto financeiro versus consumo físico, referentes ausentes etc.")
    kind: Literal["conceptual", "platform", "analytical", "hybrid", "clarification", "unsupported"]
    resolved_question: str = Field(min_length=1, max_length=1000)
    metrics: list[str] = Field(default_factory=list, max_length=8)
    locations: list[GeographicReference] = Field(default_factory=list, max_length=8)
    period: RequestedPeriod | None = None
    filters: list[str] = Field(default_factory=list, max_length=10)
    group_by: list[str] = Field(default_factory=list, max_length=6)
    comparison: str | None = Field(default=None, max_length=200)
    uses_context: bool = False
    source_ids: list[str] = Field(default_factory=list, max_length=6)


class SQLGenerationResult(BaseModel):
    status: SQLGenerationStatus
    sql: str | None = None
    reason: str | None = None
    interpretation: SemanticIntent | None = None
    knowledge_answer: str | None = Field(default=None, max_length=2500)

    @model_validator(mode="after")
    def validate_result(self):
        if self.status == SQLGenerationStatus.KNOWLEDGE:
            if self.sql is not None or self.reason is not None:
                raise ValueError("Conhecimento não executa SQL nem usa reason.")
            if (not self.knowledge_answer or not self.knowledge_answer.strip()
                    or self.interpretation is None
                    or self.interpretation.kind not in {"conceptual", "platform"}
                    or not self.interpretation.source_ids):
                raise ValueError("Conhecimento exige intenção, fontes e resposta fundamentada.")
            return self
        if self.knowledge_answer is not None and not (
            self.status == SQLGenerationStatus.READY and self.interpretation is not None
            and self.interpretation.kind == "hybrid"
        ):
            raise ValueError("knowledge_answer é exclusivo de KNOWLEDGE.")
        if self.status == SQLGenerationStatus.READY:
            if not self.sql or not self.sql.strip():
                raise ValueError(
                    "sql é obrigatório quando o status é READY."
                )

            if self.reason is not None:
                raise ValueError("reason deve ser None quando o status é READY.")

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


class InterpretedRequest(BaseModel):
    """Contrato exigido no provedor; o tipo base preserva adapters existentes."""
    # A ordem do schema importa: compreender todas as entregas antes de decidir
    # status/SQL evita que a rota inicial limite a interpretação posterior.
    interpretation: SemanticIntent
    status: SQLGenerationStatus
    sql: str | None = None
    reason: str | None = None
    knowledge_answer: str | None = Field(default=None, max_length=2500)

    @model_validator(mode="after")
    def validate_route(self):
        SQLGenerationResult.model_validate(self.model_dump())
        if self.interpretation.ambiguities and self.status in {SQLGenerationStatus.READY, SQLGenerationStatus.KNOWLEDGE}:
            # Ambiguidade de negócio não é indisponibilidade do provedor.
            self.status = SQLGenerationStatus.NEEDS_CLARIFICATION
            self.sql = self.knowledge_answer = None
            self.reason = "Preciso esclarecer: " + "; ".join(self.interpretation.ambiguities)[:230] + " Qual interpretação você deseja?"
            self.interpretation.kind = "clarification"
        if self.status == SQLGenerationStatus.READY:
            if self.interpretation.kind not in {"analytical", "hybrid"}:
                raise ValueError("READY exige intenção analítica ou híbrida.")
            if self.interpretation.kind == "hybrid" and not self.interpretation.source_ids:
                raise ValueError("Pergunta híbrida exige fontes conceituais.")
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
    UNKNOWN_TABLE = "unknown_table"
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


class SQLExecutionFlowResult(BaseModel):
    """Resultado do fluxo completo 4.1 a 4.3."""

    cached_response: "PostProcessingResult | None" = None
    interpretation: SemanticIntent | None = None
    knowledge_answer: str | None = None
    entity_resolution: str | None = None
    entity_duration_ms: float | None = None
    plan_detail: str | None = None
    generation_status: SQLGenerationStatus | None = None
    generation_reason: str | None = None
    sql: str | None = None
    guardrail_reason: SQLGuardrailReason | None = None
    outcome: SQLExecutionOutcome | None = None
    # Preserva a evidência da consulta também quando o par-check pede
    # esclarecimento após uma execução bem-sucedida com resultado vazio.
    execution_result: QueryExecutionResult | None = None
    execution_elapsed_ms: float | None = None
    provider_error: ProviderErrorType | None = None
    regenerations: int = 0
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)

    @property
    def executed(self) -> bool:
        return (
            self.outcome is not None
            and self.outcome.status == SQLExecutionStatus.SUCCESS
        )

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
    SEMANTIC_MISMATCH = "semantic_mismatch"
    SPELLED_OUT_NUMBER = "spelled_out_number"
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
    # Proveniência da resposta aprovada, preservada também no hit antes do LLM.
    source_sql: str | None = None
    interpretation: SemanticIntent | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if not self.answer or not self.answer.strip():
            raise ValueError(
                "answer é obrigatório."
            )

        return self

# =========================================================
# Auditoria,cache e finalizer — CAMADA 7
# =========================================================
class AgentOutcome(str, Enum):
    ANSWERED = "answered"
    NO_DATA = "no_data"

    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    REQUEST_REJECTED = "request_rejected"

    INPUT_BLOCKED = "input_blocked"
    SQL_BLOCKED = "sql_blocked"
    OUTPUT_BLOCKED = "output_blocked"

    PROVIDER_ERROR = "provider_error"
    EXECUTION_ERROR = "execution_error"
    INTERNAL_ERROR = "internal_error"


class AuditStepStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    ERROR = "error"
    CACHE_HIT = "cache_hit"


class AuditStep(BaseModel):
    """Resumo seguro de uma etapa do pipeline, sem conteúdo bruto da requisição."""

    code: str
    name: str
    status: AuditStepStatus
    detail: str | None = None
    duration_ms: float | None = None


class AuditRecord(BaseModel):
    request_id: str
    session_id: str | None = None

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    question: str
    outcome: AgentOutcome

    cache_hit: bool = False

    sql: str | None = None
    row_count: int | None = None
    truncated: bool | None = None

    provider_error: ProviderErrorType | None = None
    regenerations: int = 0

    # Metadados adicionais para auditoria e diagnóstico do fluxo completo.
    stage: str | None = None
    duration_ms: float | None = None
    provider_attempts: list[ProviderAttempt] = Field(default_factory=list)
    steps: list[AuditStep] = Field(default_factory=list)

    final_answer: str | None = None

class MemoryEntry(BaseModel):
    question: str
    answer: str
    outcome: AgentOutcome
    interpretation: SemanticIntent | None = None
    # Snapshot explícito do antecedente usado nesta resposta. Não é inferido
    # removendo turnos de um histórico que pode ter sido truncado ou alterado.
    context_recorded: bool = False
    context_before: str | None = Field(default=None, max_length=4000)



SQLExecutionFlowResult.model_rebuild()
