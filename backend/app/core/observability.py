"""Observabilidade opcional. Nunca inspeciona argumentos das funções instrumentadas."""

from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from functools import wraps
from inspect import iscoroutinefunction
import logging
from time import perf_counter
from uuid import uuid4


logger = logging.getLogger(__name__)
_logfire = None
_request_id: ContextVar[str | None] = ContextVar("observability_request_id", default=None)
_summary: ContextVar[dict | None] = ContextVar("observability_summary", default=None)


def request_id() -> str:
    """Reutiliza o ID do contexto interno ou gera um UUID, inclusive sem Logfire."""
    return _request_id.get() or uuid4().hex


def set_metadata(**metadata):
    if _logfire is not None:
        from app.core.telemetry_export import safe_attributes
        from opentelemetry.trace import get_current_span

        for key, value in safe_attributes(metadata).items():
            _safe_call(get_current_span().set_attribute, key, value)


def _safe_call(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except Exception:
        # Não registrar a exceção: a mensagem pode conter conteúdo da requisição/token.
        return None


class _Span:
    def __init__(self, span=None):
        self.span = span

    def set(self, **metadata):
        if self.span is None:
            return
        from app.core.telemetry_export import safe_attributes

        for key, value in safe_attributes(metadata).items():
            _safe_call(self.span.set_attribute, key, value)


@contextmanager
def span(stage: str):
    """Falhas do SDK não afetam o trabalho; exceções do trabalho são preservadas."""
    raw = None
    if _logfire is not None:
        raw = _safe_call(_logfire.span, f"agent.{stage}", stage=stage,
                         request_id=request_id())
    entered = raw is not None and _safe_call(raw.__enter__) is not None
    handle = _Span(raw if entered else None)
    start = perf_counter()
    try:
        yield handle
    except BaseException:
        handle.set(outcome="internal_error")
        raise
    finally:
        handle.set(duration_ms=(perf_counter() - start) * 1000)
        if entered:
            # Não entregar exc_info ao SDK (mensagem/stack podem carregar dados).
            _safe_call(raw.__exit__, None, None, None)


def _value(value):
    return value.value if isinstance(value, Enum) else value


def _result_metadata(stage, result):
    """Projeções explícitas: nunca serializar um resultado/erro completo."""
    metadata = {}
    summary = _summary.get()
    if stage in {"C1", "C4.2", "C5"}:
        metadata = {"outcome": _value(result.decision)}
    elif stage == "C2":
        metadata = {"cache_hit": result.cache_hit}
    elif stage in {"C4.1", "C4.4"}:
        output, attempts, error = result
        metadata = {
            "outcome": _value(error or (output.status if output is not None else "invalid_output")),
            "provider_attempts": len(attempts),
            "provider_count": len({attempt.provider for attempt in attempts}),
        }
    elif stage == "C4.3":
        metadata = {"outcome": _value(result.error_type or result.status)}
        if result.result is not None:
            metadata.update(row_count=result.result.row_count, truncated=result.result.truncated)
            if summary is not None:
                summary.update(row_count=result.result.row_count, truncated=result.result.truncated)
    elif stage in {"sql_flow", "synthesis_flow"}:
        metadata = {"regenerations": result.regenerations}
        if summary is not None:
            summary["regenerations"] = summary.get("regenerations", 0) + result.regenerations
            if stage == "sql_flow" and result.generation_status is not None:
                summary["generation_status"] = _value(result.generation_status)
    elif stage == "C6":
        metadata = {"outcome": "processed" if result is not None else "not_processed"}
    elif stage == "provider":
        attempt = result[1]
        metadata = {
            "provider": _value(attempt.provider), "model": attempt.model,
            "provider_attempt": attempt.attempt,
            "outcome": "success" if attempt.success else _value(attempt.error_type),
        }
    return metadata


def observe(stage: str):
    def decorate(function):
        def record(handle, result):
            metadata = _safe_call(_result_metadata, stage, result)
            if metadata:
                _safe_call(handle.set, **metadata)

        @wraps(function)
        async def asynchronous(*args, **kwargs):
            if _logfire is None:
                return await function(*args, **kwargs)
            with span(stage) as handle:
                result = await function(*args, **kwargs)
                record(handle, result)
                return result

        @wraps(function)
        def synchronous(*args, **kwargs):
            if _logfire is None:
                return function(*args, **kwargs)
            with span(stage) as handle:
                result = function(*args, **kwargs)
                record(handle, result)
                return result

        return asynchronous if iscoroutinefunction(function) else synchronous
    return decorate


def _pipeline_metadata(result, summary):
    outcome = _value(result.outcome)
    if outcome is None:
        outcome = {
            "input_guardrail": "input_blocked", "sql_guardrail": "sql_blocked",
            "sql_execution": "execution_error", "output_guardrail": "output_blocked",
            "post_processing": "internal_error", "synthesis": "provider_error",
        }.get(_value(result.stage), summary.get("generation_status", "provider_error"))
        if outcome == "rejected":
            outcome = "request_rejected"
        if _value(result.input_guardrail_reason) == "guardrail_internal_error":
            outcome = "internal_error"
    return {
        "request_id": result.request_id, "stage": _value(result.stage),
        "outcome": outcome, "cache_hit": result.cache_hit,
        "provider_attempts": len(result.provider_attempts),
        "provider_count": len({item.provider for item in result.provider_attempts}),
        "regenerations": summary.get("regenerations", 0),
        **{key: summary[key] for key in ("row_count", "truncated") if key in summary},
    }


def observe_pipeline(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        if _logfire is None:
            return await function(*args, **kwargs)
        token = _request_id.set(request_id())
        summary = {}
        summary_token = _summary.set(summary)
        try:
            with span("pipeline") as handle:
                result = await function(*args, **kwargs)
                metadata = _safe_call(_pipeline_metadata, result, summary)
                if metadata:
                    handle.set(**metadata)
                return result
        finally:
            _summary.reset(summary_token)
            _request_id.reset(token)
    return wrapped


class RequestContextMiddleware:
    """ID interno, sem confiar em headers externos e sem modificar respostas HTTP."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = _request_id.set(uuid4().hex)
        try:
            from opentelemetry.trace import get_current_span

            _safe_call(get_current_span().set_attribute, "request_id", request_id())
            await self.app(scope, receive, send)
        finally:
            _request_id.reset(token)


def discard_request_attributes(_request, _attributes):
    # Inclui argumentos validados e erros de validação (que podem conter o input).
    return {}


def configure_observability(app, settings) -> bool:
    """Só habilita com opt-in + token. Nenhum SDK é importado no caminho desligado."""
    global _logfire
    if not settings.logfire_enabled or not settings.logfire_token:
        return False
    if getattr(app.state, "observability_enabled", False):
        return True
    client = None
    instrumentation = None
    processor = None
    try:
        import os
        import logfire
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from app.core.telemetry_export import SafeSpanExporter, create_exporter

        # Impedir que o SDK crie um segundo exportador que contorne o filtro.
        if any(os.getenv(key) for key in (
            "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        )):
            raise ValueError("Exportador OTLP externo não suportado nesta configuração.")
        processor = BatchSpanProcessor(SafeSpanExporter(create_exporter(settings)))
        client = logfire.configure(
            local=True, send_to_logfire=False, console=False, metrics=False,
            service_name=settings.logfire_service_name,
            inspect_arguments=False, add_baggage_to_attributes=False,
            additional_span_processors=[processor],
            advanced=logfire.AdvancedOptions(
                pending_spans=False, emit_configuration_span=False, resource_detectors=[],
            ),
        )
        instrumentation = client.instrument_fastapi(
            app, capture_headers=False, record_send_receive=False, extra_spans=False,
            request_attributes_mapper=discard_request_attributes,
            http_capture_headers_server_request=[], http_capture_headers_server_response=[],
        )
        client.instrument_pydantic_ai(
            include_content=False, include_binary_content=False,
            include_model_request_parameters=False,
        )
        app.add_middleware(RequestContextMiddleware)
        _logfire = client
        app.state.observability_enabled = True
        return True
    except Exception:
        if instrumentation is not None:
            _safe_call(instrumentation.__enter__)
            _safe_call(instrumentation.__exit__, None, None, None)
        if client is not None:
            # A instrumentação global do PydanticAI pode ter sido parcialmente aplicada.
            from pydantic_ai import Agent

            _safe_call(Agent.instrument_all, False)
        if processor is not None:
            _safe_call(processor.shutdown)
        logger.warning("Observabilidade indisponível; aplicação continua sem Logfire.")
        return False
