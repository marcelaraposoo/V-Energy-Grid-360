from dataclasses import dataclass, field
from enum import Enum
from app.core.observability import observe_pipeline, request_id

from app.agent.context.loader import load_database_context
from app.agent.execution_responses import get_execution_message
from app.agent.guardrails.input_guardrail import validate_input
from app.agent.guardrails.output_text_rules import (
    contains_sql,
    contains_technical_error,
    contains_url,
    lacks_useful_content,
    leaks_prompt,
    mentions_provider_or_model,
)
from app.agent.output_responses import get_output_guardrail_message
from app.agent.post_processing_orchestrator import (
    process_approved_response,
)
from app.agent.provider_responses import get_provider_message
from app.agent.responses import get_guardrail_message
from app.agent.schemas import (
    AgentOutcome,
    GuardrailDecision,
    GuardrailReason,
    PostProcessingResult,
    ProviderAttempt,
    SQLGenerationStatus,
    SynthesisStatus,
    VisualizationSpec,
)
from app.agent.sql_execution_orchestrator import (
    generate_validate_and_execute,
)
from app.agent.synthesis_orchestrator import synthesize_and_validate
from app.agent.state.cache import should_store_in_cache, write_cache
from app.agent.state.dependencies import AgentStateDependencies, get_state_dependencies
from app.agent.state.request_state import prepare_request_state


class PipelineStatus(str, Enum):
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"


class PipelineStage(str, Enum):
    INPUT_GUARDRAIL = "input_guardrail"
    SQL_GENERATION = "sql_generation"
    SQL_GUARDRAIL = "sql_guardrail"
    SQL_EXECUTION = "sql_execution"
    SYNTHESIS = "synthesis"
    OUTPUT_GUARDRAIL = "output_guardrail"
    POST_PROCESSING = "post_processing"
    DONE = "done"


@dataclass(frozen=True)
class PipelineResult:
    """
    Resultado do fluxo completo.

    `message` é o texto que pode ser mostrado ao usuário: a resposta
    aprovada ou uma mensagem segura. `stage` diz onde o fluxo parou
    (uso interno: logs e testes), e nunca vai ao usuário.
    """

    status: PipelineStatus
    message: str
    stage: PipelineStage
    sql: str | None = None
    assumptions: tuple[str, ...] = ()
    visualization: VisualizationSpec | None = None
    # Metadado interno para o futuro mapeamento central de outcomes/auditoria.
    input_guardrail_reason: GuardrailReason | None = None
    provider_attempts: tuple[ProviderAttempt, ...] = ()
    request_id: str = field(default_factory=request_id)
    cache_hit: bool = False
    outcome: AgentOutcome | None = None


# Mensagens de perguntas que o agente decide não responder.
# Ficam aqui e não nos prompts porque são texto de produto.
_NOT_IN_SCOPE_MESSAGE = (
    "Essa pergunta está fora do que eu consigo responder com os "
    "dados da V-Energy. Posso ajudar com consumo, faturamento, "
    "interrupções e atendimento."
)
_REJECTED_MESSAGE = (
    "Não posso atender a essa solicitação."
)
_INSUFFICIENT_MESSAGE = (
    "Não tenho os dados necessários para responder a essa pergunta "
    "com segurança."
)
_GENERATION_BLOCKED_MESSAGE = (
    "Não consegui montar uma consulta segura para essa pergunta. "
    "Tente reformulá-la."
)
_CLARIFICATION_MAX_LENGTH = 300
_CLARIFICATION_FALLBACK = (
    "Preciso de mais detalhes para responder. Pode reformular a "
    "pergunta com mais informações, como período, município ou classe?"
)


def _is_safe_clarification(text: str | None) -> bool:
    if not text or lacks_useful_content(text):
        return False

    if len(text) > _CLARIFICATION_MAX_LENGTH:
        return False

    return not (
        leaks_prompt(text)
        or mentions_provider_or_model(text)
        or contains_technical_error(text)
        or contains_sql(text)
        or contains_url(text)
    )


def _no_answer(
    message: str,
    stage: PipelineStage,
    sql: str | None = None,
    *,
    input_guardrail_reason: GuardrailReason | None = None,
    provider_attempts: tuple[ProviderAttempt, ...] = (),
) -> PipelineResult:
    return PipelineResult(
        status=PipelineStatus.NO_ANSWER,
        message=message,
        stage=stage,
        sql=sql,
        input_guardrail_reason=input_guardrail_reason,
        provider_attempts=provider_attempts,
    )


def _generation_message(flow) -> str:
    status = flow.generation_status

    if status == SQLGenerationStatus.OUT_OF_SCOPE:
        return _NOT_IN_SCOPE_MESSAGE

    if status == SQLGenerationStatus.REJECTED:
        return _REJECTED_MESSAGE

    if status == SQLGenerationStatus.INSUFFICIENT_CONTEXT:
        return _INSUFFICIENT_MESSAGE

    if status == SQLGenerationStatus.NEEDS_CLARIFICATION:
        reason = flow.generation_reason

        if _is_safe_clarification(reason):
            return reason

        return _CLARIFICATION_FALLBACK

    return _INSUFFICIENT_MESSAGE


@observe_pipeline
async def answer_question(
    question: str,
    *,
    memory_context: str | None = None,
    database_path: str | None = None,
    session_id: str | None = None,
    state_dependencies: AgentStateDependencies | None = None,
) -> PipelineResult:
    """
    Fluxo completo do agente:

    Input Guardrail → C2 GET/HIT → 4.1 geração → 4.2 guardrail do SQL →
    4.3 execução → 4.4 síntese → Camada 5 → Camada 6 → C2 SET elegível.

    Qualquer etapa que falhar devolve uma mensagem segura, que não
    revela provedor, SQL de erro, prompt nem detalhes internos.
    """

    # ----- Camada 1: entrada -----
    entry = validate_input(question)

    if entry.decision != GuardrailDecision.ALLOW:
        return _no_answer(
            get_guardrail_message(entry.reason),
            PipelineStage.INPUT_GUARDRAIL,
            input_guardrail_reason=entry.reason,
        )

    clean_question = entry.normalized_input or question

    # ----- Camada 2: contexto efetivo e chave imutável desta requisição -----
    dependencies = state_dependencies if state_dependencies is not None else get_state_dependencies()
    state = await prepare_request_state(
        normalized_question=clean_question,
        session_id=session_id,
        dependencies=dependencies,
        memory_context=memory_context,
    )
    if state.cached_response is not None:
        cached = state.cached_response
        return PipelineResult(
            status=PipelineStatus.ANSWERED,
            message=cached.answer,
            stage=PipelineStage.DONE,
            assumptions=tuple(cached.assumptions),
            visualization=cached.visualization,
            cache_hit=True,
            outcome=AgentOutcome.ANSWERED,
        )

    # ----- 4.1, 4.2 e 4.3 -----
    flow = await generate_validate_and_execute(
        question=clean_question,
        database_context=load_database_context(),
        memory_context=state.memory_context,
        database_path=database_path,
    )

    provider_attempts = tuple(flow.provider_attempts)

    if flow.provider_error is not None:
        return _no_answer(
            get_provider_message(flow.provider_error),
            PipelineStage.SQL_GENERATION,
            provider_attempts=provider_attempts,
        )

    if flow.guardrail_reason is not None:
        return _no_answer(
            _GENERATION_BLOCKED_MESSAGE,
            PipelineStage.SQL_GUARDRAIL,
            provider_attempts=provider_attempts,
        )

    if flow.outcome is None:
        return _no_answer(
            _generation_message(flow),
            PipelineStage.SQL_GENERATION,
            provider_attempts=provider_attempts,
        )

    if not flow.executed:
        return _no_answer(
            get_execution_message(flow.outcome.error_type),
            PipelineStage.SQL_EXECUTION,
            provider_attempts=provider_attempts,
        )

    query_result = flow.outcome.result

    # ----- 4.4 e Camada 5 -----
    synthesis_flow = await synthesize_and_validate(
        question=clean_question,
        sql=flow.sql,
        result=query_result,
    )

    provider_attempts += tuple(
        item.model_copy(update={"attempt": index})
        for index, item in enumerate(synthesis_flow.provider_attempts, len(provider_attempts) + 1)
    )

    if synthesis_flow.provider_error is not None:
        return _no_answer(
            get_provider_message(synthesis_flow.provider_error),
            PipelineStage.SYNTHESIS,
            provider_attempts=provider_attempts,
        )

    if not synthesis_flow.approved:
        reason = (
            synthesis_flow.guardrail.reason
            if synthesis_flow.guardrail is not None
            else None
        )

        return _no_answer(
            get_output_guardrail_message(reason),
            PipelineStage.OUTPUT_GUARDRAIL,
            provider_attempts=provider_attempts,
        )

    # ----- Camada 6 -----
    processed: PostProcessingResult | None = process_approved_response(
        flow=synthesis_flow,
        result=query_result,
    )

    if processed is None:
        return _no_answer(
            get_output_guardrail_message(None),
            PipelineStage.POST_PROCESSING,
            provider_attempts=provider_attempts,
        )

    outcome = (
        AgentOutcome.ANSWERED
        if synthesis_flow.synthesis.status == SynthesisStatus.ANSWERED
        else AgentOutcome.NO_DATA
    )
    if (
        dependencies.cache_store is not None
        and state.cache_key is not None
        and should_store_in_cache(
            outcome,
            truncated=query_result.truncated,
            response_complete=(
                synthesis_flow.approved
                and synthesis_flow.synthesis.status == SynthesisStatus.ANSWERED
                and query_result.row_count == len(query_result.rows)
            ),
        )
    ):
        await write_cache(
            dependencies.cache_store,
            state.cache_key,
            processed,
            ttl_seconds=dependencies.cache_ttl_seconds,
            timeout_seconds=dependencies.cache_timeout_seconds,
        )

    return PipelineResult(
        status=PipelineStatus.ANSWERED,
        message=processed.answer,
        stage=PipelineStage.DONE,
        sql=flow.sql,
        assumptions=tuple(processed.assumptions),
        visualization=processed.visualization,
        provider_attempts=provider_attempts,
        outcome=outcome,
    )
