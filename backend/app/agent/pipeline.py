from app.agent.providers.latency_policy import provider_request
import logging
from dataclasses import dataclass, replace
from enum import Enum
from time import perf_counter
from app.core.observability import observe_pipeline, request_id as observability_request_id

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
    AuditStep,
    AuditStepStatus,
    GuardrailDecision,
    GuardrailReason,
    PostProcessingResult,
    OutputGuardrailReason,
    SQLGuardrailReason,
    ProviderAttempt,
    SQLGenerationStatus,
    SynthesisStatus,
    VisualizationSpec,
    QueryExecutionResult,
    OutputGuardrailDecision,
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
    audit_steps: tuple[AuditStep, ...] = ()
    duration_ms: float = 0.0
    row_count: int | None = None
    truncated: bool | None = None
    audit_persisted: bool | None = None
    regenerations: int = 0
    source_ids: tuple[str, ...] = ()


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
@provider_request
async def answer_question(
    question: str,
    *,
    memory_context: str | None = None,
    database_path: str | None = None,
    session_id: str | None = None,
    state_dependencies: AgentStateDependencies | None = None,
) -> PipelineResult:
    """C1 → C2 GET → agente se MISS → C7 (auditoria, memória, SET) → entrega."""
    request_id = observability_request_id()
    started_at = perf_counter()
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
    provider_attempts: tuple[ProviderAttempt, ...] = ()
    audit_steps: list[AuditStep] = []
    interpretation = None

    def add_audit_step(
        code: str,
        name: str,
        status: AuditStepStatus,
        detail: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        audit_steps.append(AuditStep(
            code=code, name=name, status=status,
            detail=detail, duration_ms=duration_ms,
        ))

    async def finish(result: PipelineResult, outcome: AgentOutcome) -> PipelineResult:
        if interpretation is not None:
            from app.core.observability import set_metadata
            set_metadata(intent_kind=interpretation.kind)
            result = replace(result, source_ids=tuple(interpretation.source_ids))
            if processed is not None:
                processed.interpretation = interpretation
                processed.source_sql = executed_sql
        elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
        attempts = tuple(result.provider_attempts or provider_attempts)

        # C3 agrupa as tentativas registradas pelo roteador, nas fases SQL e síntese.
        if not any(item.code == "C3" for item in audit_steps):
            providers = sorted({item.provider.value for item in attempts})
            if provider_error is not None:
                c3_status = AuditStepStatus.ERROR
            elif attempts:
                c3_status = AuditStepStatus.COMPLETED
            else:
                c3_status = AuditStepStatus.SKIPPED
            detail = (
                f"{len(attempts)} tentativa(s); provedores: {', '.join(providers)}."
                if attempts else "Nenhuma chamada a provedor nesta execução."
            )
            add_audit_step("C3", "Seleção e fallback de provedores", c3_status, detail)

        # Mantém uma linha para cada etapa, inclusive quando o fluxo é bloqueado cedo.
        names = {
            "C1": "Validação de entrada",
            "C2": "Cache e memória conversacional",
            "C3": "Seleção e fallback de provedores",
            "C4.1": "Interpretação e planejamento",
            "C4.2": "Validação de SQL",
            "C4.3": "Execução SQL",
            "C4.4": "Síntese da resposta",
            "C5": "Validação da resposta",
            "C6": "Pós-processamento",
        }
        present = {item.code for item in audit_steps}
        for code, name in names.items():
            if code not in present:
                add_audit_step(
                    code, name, AuditStepStatus.SKIPPED,
                    "Etapa não executada neste fluxo.",
                )

        # O registro de auditoria é a própria evidência de entrada na C7.
        ordered_steps = sorted(
            audit_steps,
            key=lambda item: (list(names).index(item.code) if item.code in names else len(names)),
        )
        c7_attempt = AuditStep(
            code="C7", name="Finalização e persistência da auditoria",
            status=AuditStepStatus.COMPLETED,
            detail="Registro enviado à camada de persistência.",
        )
        steps_for_record = tuple([*ordered_steps, c7_attempt])

        audit_persisted: bool | None = None
        if dependencies is not None:
            try:
                # A finalização também atualiza memória/cache quando a auditoria
                # SQLite está desabilitada em uma configuração de teste ou ambiente.
                audit_persisted = await finalize_request(
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
                    stage=result.stage.value,
                    duration_ms=elapsed_ms,
                    provider_attempts=attempts,
                    steps=steps_for_record,
                    interpretation=interpretation,
                    context_recorded=interpretation is not None and state is not None and state.memory_status != MemoryContextStatus.UNAVAILABLE,
                    context_before=state.memory_context if state is not None else None,
                )
            except Exception as error:
                audit_persisted = False
                # Falha de auditoria nunca substitui a resposta segura do agente.
                logger.warning("Falha na finalização. error_type=%s", type(error).__name__)
        else:
            # O factory de estado falhou antes de disponibilizar os stores.
            audit_persisted = None

        final_c7 = AuditStep(
            code="C7", name="Finalização e persistência da auditoria",
            status=(
                AuditStepStatus.COMPLETED if audit_persisted is True
                else AuditStepStatus.ERROR if audit_persisted is False
                else AuditStepStatus.SKIPPED
            ),
            detail=(
                "Registro persistido em portal.db."
                if audit_persisted is True
                else "Não foi possível persistir o registro de auditoria."
                if audit_persisted is False
                else "Armazenamento de auditoria indisponível nesta execução."
            ),
        )
        final_steps = tuple([*ordered_steps, final_c7])
        return replace(
            result,
            request_id=request_id,
            outcome=outcome,
            provider_attempts=attempts,
            audit_steps=final_steps,
            duration_ms=elapsed_ms,
            row_count=query_result.row_count if query_result is not None else None,
            truncated=query_result.truncated if query_result is not None else None,
            audit_persisted=audit_persisted,
            regenerations=regenerations,
        )

    try:
        # Settings continua validado no import de app.main (fail-fast no startup).
        # Falhas do factory durante uma requisição recebem a mensagem segura abaixo.
        if dependencies is None:
            dependencies = get_state_dependencies()
        c1_started = perf_counter()
        entry = validate_input(question)
        c1_duration = round((perf_counter() - c1_started) * 1000, 2)
        if entry.decision != GuardrailDecision.ALLOW:
            add_audit_step(
                "C1", "Validação de entrada",
                AuditStepStatus.ERROR if entry.reason == GuardrailReason.GUARDRAIL_INTERNAL_ERROR else AuditStepStatus.BLOCKED,
                entry.reason.value if entry.reason else "Entrada bloqueada.", c1_duration,
            )
            outcome = (
                AgentOutcome.INTERNAL_ERROR
                if entry.reason == GuardrailReason.GUARDRAIL_INTERNAL_ERROR
                else AgentOutcome.INPUT_BLOCKED
            )
            return await finish(_no_answer(
                get_guardrail_message(entry.reason), stage,
                input_guardrail_reason=entry.reason,
            ), outcome)

        add_audit_step(
            "C1", "Validação de entrada", AuditStepStatus.COMPLETED,
            "Entrada normalizada e aprovada pela C1.", c1_duration,
        )
        clean_question = entry.normalized_input or question
        c2_started = perf_counter()
        state = await prepare_request_state(
            normalized_question=clean_question,
            session_id=session_id,
            dependencies=dependencies,
            memory_context=memory_context,
        )
        c2_duration = round((perf_counter() - c2_started) * 1000, 2)
        if state.cached_response is not None:
            c2_detail = "Resposta recuperada do cache."
            c2_status = AuditStepStatus.CACHE_HIT
        elif dependencies.cache_store is None:
            c2_detail = f"Cache desabilitado por configuração; contexto de memória: {state.memory_status.value}."
            c2_status = AuditStepStatus.SKIPPED
        elif not session_id or not session_id.strip():
            c2_detail = f"Cache não consultado: sessão ausente; contexto de memória: {state.memory_status.value}."
            c2_status = AuditStepStatus.SKIPPED
        elif state.memory_status == MemoryContextStatus.UNAVAILABLE:
            c2_detail = "Cache não consultado porque a leitura da memória da sessão falhou."
            c2_status = AuditStepStatus.ERROR
        elif state.cache_key is None:
            c2_detail = f"Cache não consultado; chave indisponível. Contexto de memória: {state.memory_status.value}."
            c2_status = AuditStepStatus.SKIPPED
        else:
            c2_detail = f"Cache consultado sem resposta reutilizável; contexto de memória: {state.memory_status.value}."
            c2_status = AuditStepStatus.COMPLETED
        add_audit_step(
            "C2", "Cache e memória conversacional", c2_status,
            c2_detail, c2_duration,
        )
        if state.cached_response is not None:
            cached = state.cached_response
            executed_sql = cached.source_sql
            interpretation = cached.interpretation
            if interpretation is not None:
                add_audit_step("INTENT", "Intenção e fontes da resposta em cache", AuditStepStatus.CACHE_HIT,
                               interpretation.model_dump_json())
            return await finish(PipelineResult(
                status=PipelineStatus.ANSWERED,
                message=cached.answer,
                stage=PipelineStage.DONE,
                assumptions=tuple(cached.assumptions),
                visualization=cached.visualization,
                cache_hit=True,
                sql=cached.source_sql,
            ), AgentOutcome.ANSWERED)

        lookup_options = {}
        if (state.cache_key is not None and callable(getattr(dependencies.cache_store, "get_plan", None))):
            async def lookup_plan(sql, interpretation=None):
                from app.agent.state.sql_cache import lookup_sql_cache
                lookup = await lookup_sql_cache(
                    dependencies.cache_store, question=clean_question, sql=sql,
                    session_id=session_id, data_version=dependencies.data_version,
                    timeout_seconds=dependencies.cache_timeout_seconds,
                )
                if lookup.response is not None and interpretation is not None:
                    previous = lookup.response.interpretation
                    if previous is None or previous.model_dump(exclude={'uses_context'}) != interpretation.model_dump(exclude={'uses_context'}):
                        from app.agent.state.sql_cache import record_cache
                        record_cache('intent_changed', 'post_sql')
                        return None
                return lookup.response
            lookup_options["cache_lookup"] = lookup_plan
        stage = PipelineStage.SQL_GENERATION
        from app.agent.context.runtime import build_runtime_context
        import asyncio
        metadata_started = perf_counter()
        runtime_context = await asyncio.to_thread(build_runtime_context, clean_question, database_path)
        catalog_unavailable = '"catalogo_disponivel": false' in runtime_context
        add_audit_step("METADATA", "Metadados do catálogo", AuditStepStatus.ERROR if catalog_unavailable else AuditStepStatus.COMPLETED,
                       "Catálogo indisponível; isso não comprova ausência de dados." if catalog_unavailable else "Calendário, cobertura e cadastro consultados em modo somente leitura.",
                       round((perf_counter() - metadata_started) * 1000, 2))
        sql_started = perf_counter()
        flow = await generate_validate_and_execute(
            question=clean_question,
            database_context=load_database_context() + runtime_context,
            memory_context=state.memory_context,
            database_path=database_path,
            **lookup_options,
        )
        provider_attempts = tuple(flow.provider_attempts)
        interpretation = flow.interpretation
        if interpretation is not None:
            add_audit_step("INTENT", "Intenção, operação e fontes", AuditStepStatus.COMPLETED,
                           interpretation.model_dump_json())
        if flow.entity_resolution is not None:
            add_audit_step("ENTITIES", "Resolução geográfica",
                           AuditStepStatus.ERROR if flow.entity_resolution == "technical_failure" else AuditStepStatus.COMPLETED,
                           flow.entity_resolution, flow.entity_duration_ms)
        if flow.plan_detail:
            add_audit_step("PLAN", "Plano de consulta", AuditStepStatus.COMPLETED, flow.plan_detail)
        executed_sql = flow.sql  # SQL validado também é relevante quando o resultado veio do cache pós-SQL.
        query_result = flow.execution_result or (
            flow.outcome.result if flow.outcome is not None else None
        )
        provider_error = flow.provider_error
        regenerations = flow.regenerations

        if provider_error is not None:
            add_audit_step(
                "C4.1", "Geração SQL", AuditStepStatus.ERROR,
                f"A geração SQL falhou: {provider_error.value}.",
                round((perf_counter() - sql_started) * 1000, 2),
            )
        elif flow.generation_status in {SQLGenerationStatus.READY, SQLGenerationStatus.KNOWLEDGE}:
            add_audit_step(
                "C4.1", "Interpretação e planejamento", AuditStepStatus.COMPLETED,
                "Operação selecionada: " + ("consulta SQL" if flow.sql else "conhecimento documentado") + ".",
                round(sum(a.latency_ms or 0 for a in provider_attempts), 2),
            )
        else:
            generation_detail = (
                flow.generation_status.value if flow.generation_status is not None
                else "A geração não produziu uma consulta utilizável."
            )
            add_audit_step(
                "C4.1", "Geração SQL", AuditStepStatus.BLOCKED,
                generation_detail,
            )

        if flow.guardrail_reason is not None:
            add_audit_step(
                "C4.2", "Validação de SQL", AuditStepStatus.BLOCKED,
                flow.guardrail_reason.value,
            )
        elif flow.sql is not None:
            add_audit_step(
                "C4.2", "Validação de SQL", AuditStepStatus.COMPLETED,
                "Consulta aprovada pelas regras de segurança SQL.",
            )

        if flow.outcome is not None:
            add_audit_step(
                "C4.3", "Execução SQL",
                AuditStepStatus.COMPLETED if flow.executed else AuditStepStatus.ERROR,
                (
                    f"{flow.outcome.result.row_count} linha(s) retornada(s)."
                    if flow.executed and flow.outcome.result is not None
                    else (flow.outcome.error_type.value if flow.outcome.error_type else "Falha na execução SQL.")
                ),
                round(flow.outcome.elapsed_ms, 2),
            )
        elif flow.execution_result is not None:
            add_audit_step(
                "C4.3", "Execução SQL", AuditStepStatus.COMPLETED,
                f"Consulta executada; {flow.execution_result.row_count} linha(s) retornada(s). O fluxo solicitou esclarecimento após validar a combinação de filtros.",
                round(flow.execution_elapsed_ms, 2) if flow.execution_elapsed_ms is not None else None,
            )
        elif flow.cached_response is not None:
            add_audit_step(
                "C4.3", "Execução SQL", AuditStepStatus.CACHE_HIT,
                "Resultado recuperado do cache SQL; execução física dispensada.",
            )
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

        if flow.cached_response is not None:
            cached = flow.cached_response
            interpretation = cached.interpretation or interpretation
            return await finish(PipelineResult(
                status=PipelineStatus.ANSWERED, message=cached.answer,
                stage=PipelineStage.DONE, sql=flow.sql,
                assumptions=tuple(cached.assumptions),
                visualization=cached.visualization, cache_hit=True,
                provider_attempts=provider_attempts,
            ), AgentOutcome.ANSWERED)

        if flow.generation_status == SQLGenerationStatus.KNOWLEDGE:
            from app.agent.context.knowledge import source_text
            from app.agent.guardrails.output_guardrail import validate_output
            if interpretation is None or not flow.knowledge_answer:
                return await finish(_no_answer(_INSUFFICIENT_MESSAGE, stage), AgentOutcome.INTERNAL_ERROR)
            evidence = source_text(interpretation.source_ids)
            # Contexto vazio de valores operacionais para o guardrail; nenhuma
            # consulta foi executada nem é registrada como executada.
            approved = validate_output(flow.knowledge_answer, [], clean_question, "",
                                       QueryExecutionResult(columns=[], rows=[], row_count=0),
                                       knowledge_text=evidence, structured_intent=True)
            add_audit_step("C5", "Validação da resposta", AuditStepStatus.COMPLETED
                           if approved.decision == OutputGuardrailDecision.ALLOW else AuditStepStatus.BLOCKED,
                           approved.reason.value if approved.reason else "Fontes documentais autorizadas e validações de texto/números aplicadas.")
            if approved.decision != OutputGuardrailDecision.ALLOW:
                return await finish(_no_answer(get_output_guardrail_message(approved.reason), PipelineStage.OUTPUT_GUARDRAIL), AgentOutcome.OUTPUT_BLOCKED)
            processed = PostProcessingResult(answer=flow.knowledge_answer)
            response_complete = True
            add_audit_step("C6", "Pós-processamento", AuditStepStatus.COMPLETED, "Explicação fundamentada nas fontes selecionadas.")
            return await finish(PipelineResult(status=PipelineStatus.ANSWERED, message=processed.answer,
                                               stage=PipelineStage.DONE), AgentOutcome.ANSWERED)

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
        synthesis_started = perf_counter()
        synthesis_options = {}
        if interpretation is not None:
            from app.agent.context.knowledge import source_text
            synthesis_options["structured_intent"] = True
            if interpretation.source_ids:
                synthesis_options["knowledge_text"] = source_text(interpretation.source_ids)
        synthesis_flow = await synthesize_and_validate(
            question=clean_question, sql=flow.sql, result=query_result,
            **synthesis_options,
        )
        regenerations += synthesis_flow.regenerations
        provider_attempts += tuple(
            item.model_copy(update={"attempt": index})
            for index, item in enumerate(synthesis_flow.provider_attempts, len(provider_attempts) + 1)
        )
        provider_error = synthesis_flow.provider_error
        if synthesis_flow.provider_error is not None:
            add_audit_step(
                "C4.4", "Síntese da resposta", AuditStepStatus.ERROR,
                f"A síntese falhou: {provider_error.value}.",
                round((perf_counter() - synthesis_started) * 1000, 2),
            )
        elif synthesis_flow.synthesis is not None:
            add_audit_step(
                "C4.4", "Síntese da resposta", AuditStepStatus.COMPLETED,
                f"Síntese gerada: {synthesis_flow.synthesis.status.value}.",
                round((perf_counter() - synthesis_started) * 1000, 2),
            )
        else:
            add_audit_step(
                "C4.4", "Síntese da resposta", AuditStepStatus.ERROR,
                "A síntese não produziu uma saída válida.",
            )

        if synthesis_flow.provider_error is None and synthesis_flow.synthesis is not None:
            add_audit_step(
                "C5", "Validação da resposta",
                AuditStepStatus.COMPLETED if synthesis_flow.approved else AuditStepStatus.BLOCKED,
                "Resposta aprovada pelo Output Guardrail."
                if synthesis_flow.approved else "Resposta bloqueada pelo Output Guardrail.",
            )
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
        post_started = perf_counter()
        processed = process_approved_response(flow=synthesis_flow, result=query_result)
        post_duration = round((perf_counter() - post_started) * 1000, 2)
        if processed is None:
            add_audit_step(
                "C6", "Pós-processamento", AuditStepStatus.ERROR,
                "Não foi possível preparar a resposta aprovada.", post_duration,
            )
            return await finish(_no_answer(
                get_output_guardrail_message(None), stage,
                provider_attempts=provider_attempts,
            ), AgentOutcome.INTERNAL_ERROR)

        add_audit_step(
            "C6", "Pós-processamento", AuditStepStatus.COMPLETED,
            "Resposta e visualização preparadas a partir do resultado SQL.", post_duration,
        )
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
