from dataclasses import dataclass
from enum import Enum

from app.agent.context.loader import load_database_context
from app.agent.execution_responses import get_execution_message
from app.agent.guardrails.input_guardrail import validate_input
from app.agent.output_responses import get_output_guardrail_message
from app.agent.post_processing_orchestrator import (
    process_approved_response,
)
from app.agent.provider_responses import get_provider_message
from app.agent.responses import get_guardrail_message
from app.agent.schemas import (
    GuardrailDecision,
    PostProcessingResult,
    SQLGenerationStatus,
    SynthesisStatus,
    VisualizationSpec,
)
from app.agent.sql_execution_orchestrator import (
    generate_validate_and_execute,
)
from app.agent.synthesis_orchestrator import synthesize_and_validate


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


def _no_answer(
    message: str,
    stage: PipelineStage,
    sql: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        status=PipelineStatus.NO_ANSWER,
        message=message,
        stage=stage,
        sql=sql,
    )


def _generation_message(flow) -> str:
    status = flow.generation_status

    if status == SQLGenerationStatus.OUT_OF_SCOPE:
        return _NOT_IN_SCOPE_MESSAGE

    if status == SQLGenerationStatus.REJECTED:
        return _REJECTED_MESSAGE

    if status == SQLGenerationStatus.INSUFFICIENT_CONTEXT:
        return _INSUFFICIENT_MESSAGE

    # NEEDS_CLARIFICATION: a própria pergunta de volta ao usuário.
    return flow.generation_reason or _INSUFFICIENT_MESSAGE


async def answer_question(
    question: str,
    *,
    memory_context: str | None = None,
    database_path: str | None = None,
) -> PipelineResult:
    """
    Fluxo completo do agente:

    Input Guardrail → 4.1 geração → 4.2 guardrail do SQL →
    4.3 execução → 4.4 síntese → Camada 5 → Camada 6.

    Qualquer etapa que falhar devolve uma mensagem segura, que não
    revela provedor, SQL de erro, prompt nem detalhes internos.
    """

    # ----- Camada 1: entrada -----
    entry = validate_input(question)

    if entry.decision != GuardrailDecision.ALLOW:
        return _no_answer(
            get_guardrail_message(entry.reason),
            PipelineStage.INPUT_GUARDRAIL,
        )

    clean_question = entry.normalized_input or question

    # ----- 4.1, 4.2 e 4.3 -----
    flow = await generate_validate_and_execute(
        question=clean_question,
        database_context=load_database_context(),
        memory_context=memory_context,
        database_path=database_path,
    )

    if flow.provider_error is not None:
        return _no_answer(
            get_provider_message(flow.provider_error),
            PipelineStage.SQL_GENERATION,
        )

    if flow.guardrail_reason is not None:
        return _no_answer(
            _GENERATION_BLOCKED_MESSAGE,
            PipelineStage.SQL_GUARDRAIL,
        )

    if flow.outcome is None:
        return _no_answer(
            _generation_message(flow),
            PipelineStage.SQL_GENERATION,
        )

    if not flow.executed:
        return _no_answer(
            get_execution_message(flow.outcome.error_type),
            PipelineStage.SQL_EXECUTION,
        )

    query_result = flow.outcome.result

    # ----- 4.4 e Camada 5 -----
    synthesis_flow = await synthesize_and_validate(
        question=clean_question,
        sql=flow.sql,
        result=query_result,
    )

    if synthesis_flow.provider_error is not None:
        return _no_answer(
            get_provider_message(synthesis_flow.provider_error),
            PipelineStage.SYNTHESIS,
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
        )

    return PipelineResult(
        status=PipelineStatus.ANSWERED,
        message=processed.answer,
        stage=PipelineStage.DONE,
        sql=flow.sql,
        assumptions=tuple(processed.assumptions),
        visualization=processed.visualization,
    )