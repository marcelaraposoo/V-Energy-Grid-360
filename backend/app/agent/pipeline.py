import logging
from dataclasses import dataclass, replace
from enum import Enum
from uuid import uuid4

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
    OutputGuardrailReason,
    SQLGuardrailReason,
    ProviderAttempt,
    SQLGenerationStatus,
    SynthesisStatus,
    VisualizationSpec,
)
from app.agent.sql_execution_orchestrator import (
    generate_validate_and_execute,
)
from app.agent.synthesis_orchestrator import synthesize_and_validate
from app.agent.state.service import finalize_request
from app.agent.state.dependencies import AgentStateDependencies, get_state_dependencies
from app.agent.state.request_state import MemoryContextStatus, prepare_request_state


logger = logging.getLogger(__name__)


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
    # Metadados internos da requisição atual e da finalização C7.
    input_guardrail_reason: GuardrailReason | None = None
    provider_attempts: tuple[ProviderAttempt, ...] = ()
    request_id: str = ""
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


async def answer_question(
    question: str,
    *,
    memory_context: str | None = None,
    database_path: str | None = None,
    session_id: str | None = None,
    state_dependencies: AgentStateDependencies | None = None,
) -> PipelineResult:
    """C1 → C2 GET → agente se MISS → C7 (auditoria, memória, SET) → entrega."""
    request_id = uuid4().hex
    dependencies = state_dependencies
    state = None
    clean_question = question
    executed_sql = None
    query_result = None
    provider_error = None
    regenerations = 0
    processed = None
    response_complete = False
    stage = PipelineStage.INPUT_GUARDRAIL

    async def finish(result: PipelineResult, outcome: AgentOutcome) -> PipelineResult:
        result = replace(result, request_id=request_id, outcome=outcome)
        if dependencies is None:
            # O factory falhou: não há stores válidos para finalizar a requisição.
            return result
        try:
            await finalize_request(
                audit_store=dependencies.audit_store,
                request_id=request_id,
                question=clean_question,
                session_id=session_id,
                outcome=outcome,
                final_answer=result.message,
                sql=executed_sql,
                query_result=query_result,
                provider_error=provider_error,
                regenerations=regenerations,
                cache_hit=result.cache_hit,
                memory_store=(
                    dependencies.memory_store
                    if state is not None and state.memory_status != MemoryContextStatus.UNAVAILABLE
                    else None
                ),
                memory_timeout_seconds=dependencies.memory_timeout_seconds,
                cache_store=dependencies.cache_store,
                cache_key=state.cache_key if state is not None else None,
                cache_value=processed,
                cache_ttl_seconds=dependencies.cache_ttl_seconds,
                cache_timeout_seconds=dependencies.cache_timeout_seconds,
                cache_data_version=dependencies.data_version,
                cache_response_complete=response_complete,
            )
        except Exception as error:
            # Defesa da fronteira: uma falha de construção/finalização também
            # não pode substituir a resposta aprovada ou sua mensagem segura.
            logger.warning("Falha na finalização. error_type=%s", type(error).__name__)
        return result

    try:
        # Settings continua validado no import de app.main (fail-fast no startup).
        # Falhas do factory durante uma requisição recebem a mensagem segura abaixo.
        if dependencies is None:
            dependencies = get_state_dependencies()
        entry = validate_input(question)
        if entry.decision != GuardrailDecision.ALLOW:
            outcome = (
                AgentOutcome.INTERNAL_ERROR
                if entry.reason == GuardrailReason.GUARDRAIL_INTERNAL_ERROR
                else AgentOutcome.INPUT_BLOCKED
            )
            return await finish(_no_answer(
                get_guardrail_message(entry.reason), stage,
                input_guardrail_reason=entry.reason,
            ), outcome)

        clean_question = entry.normalized_input or question
        state = await prepare_request_state(
            normalized_question=clean_question,
            session_id=session_id,
            dependencies=dependencies,
            memory_context=memory_context,
        )
        if state.cached_response is not None:
            cached = state.cached_response
            return await finish(PipelineResult(
                status=PipelineStatus.ANSWERED,
                message=cached.answer,
                stage=PipelineStage.DONE,
                assumptions=tuple(cached.assumptions),
                visualization=cached.visualization,
                cache_hit=True,
            ), AgentOutcome.ANSWERED)

        stage = PipelineStage.SQL_GENERATION
        flow = await generate_validate_and_execute(
            question=clean_question,
            database_context=load_database_context(),
            memory_context=state.memory_context,
            database_path=database_path,
        )
        provider_attempts = tuple(flow.provider_attempts)
        executed_sql = flow.sql
        provider_error = flow.provider_error
        regenerations = flow.regenerations
        if provider_error is not None:
            return await finish(_no_answer(
                get_provider_message(provider_error), stage,
                provider_attempts=provider_attempts,
            ), AgentOutcome.PROVIDER_ERROR)

        if flow.guardrail_reason is not None:
            outcome = (
                AgentOutcome.INTERNAL_ERROR
                if flow.guardrail_reason == SQLGuardrailReason.GUARDRAIL_INTERNAL_ERROR
                else AgentOutcome.SQL_BLOCKED
            )
            return await finish(_no_answer(
                _GENERATION_BLOCKED_MESSAGE, PipelineStage.SQL_GUARDRAIL,
                provider_attempts=provider_attempts,
            ), outcome)

        if flow.outcome is None:
            outcomes = {
                SQLGenerationStatus.NEEDS_CLARIFICATION: AgentOutcome.NEEDS_CLARIFICATION,
                SQLGenerationStatus.OUT_OF_SCOPE: AgentOutcome.OUT_OF_SCOPE,
                SQLGenerationStatus.INSUFFICIENT_CONTEXT: AgentOutcome.INSUFFICIENT_CONTEXT,
                SQLGenerationStatus.REJECTED: AgentOutcome.REQUEST_REJECTED,
            }
            return await finish(_no_answer(
                _generation_message(flow), stage, provider_attempts=provider_attempts,
            ), outcomes.get(flow.generation_status, AgentOutcome.INTERNAL_ERROR))

        if not flow.executed:
            return await finish(_no_answer(
                get_execution_message(flow.outcome.error_type), PipelineStage.SQL_EXECUTION,
                provider_attempts=provider_attempts,
            ), AgentOutcome.EXECUTION_ERROR)

        query_result = flow.outcome.result
        stage = PipelineStage.SYNTHESIS
        synthesis_flow = await synthesize_and_validate(
            question=clean_question, sql=flow.sql, result=query_result,
        )
        regenerations += synthesis_flow.regenerations
        provider_attempts += tuple(
            item.model_copy(update={"attempt": index})
            for index, item in enumerate(synthesis_flow.provider_attempts, len(provider_attempts) + 1)
        )
        provider_error = synthesis_flow.provider_error
        if provider_error is not None:
            return await finish(_no_answer(
                get_provider_message(provider_error), stage,
                provider_attempts=provider_attempts,
            ), AgentOutcome.PROVIDER_ERROR)

        if not synthesis_flow.approved:
            reason = synthesis_flow.guardrail.reason if synthesis_flow.guardrail is not None else None
            outcome = (
                AgentOutcome.INTERNAL_ERROR
                if reason is None or reason == OutputGuardrailReason.GUARDRAIL_INTERNAL_ERROR
                else AgentOutcome.OUTPUT_BLOCKED
            )
            return await finish(_no_answer(
                get_output_guardrail_message(reason), PipelineStage.OUTPUT_GUARDRAIL,
                provider_attempts=provider_attempts,
            ), outcome)

        stage = PipelineStage.POST_PROCESSING
        processed = process_approved_response(flow=synthesis_flow, result=query_result)
        if processed is None:
            return await finish(_no_answer(
                get_output_guardrail_message(None), stage,
                provider_attempts=provider_attempts,
            ), AgentOutcome.INTERNAL_ERROR)

        outcome = (
            AgentOutcome.ANSWERED
            if synthesis_flow.synthesis.status == SynthesisStatus.ANSWERED
            else AgentOutcome.NO_DATA
        )
        response_complete = (
            synthesis_flow.approved
            and synthesis_flow.synthesis.status == SynthesisStatus.ANSWERED
            and query_result.row_count == len(query_result.rows)
        )
        return await finish(PipelineResult(
            status=PipelineStatus.ANSWERED,
            message=processed.answer,
            stage=PipelineStage.DONE,
            sql=flow.sql,
            assumptions=tuple(processed.assumptions),
            visualization=processed.visualization,
            provider_attempts=provider_attempts,
        ), outcome)
    except Exception as error:
        logger.warning("Falha no pipeline. error_type=%s", type(error).__name__)
        return await finish(_no_answer(
            "Não foi possível responder neste momento. Tente novamente.", stage,
        ), AgentOutcome.INTERNAL_ERROR)
