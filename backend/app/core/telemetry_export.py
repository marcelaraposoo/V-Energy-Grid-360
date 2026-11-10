"""Único caminho de exportação: filtra atributos, nomes, recursos e exceções."""

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import Status


TEXT_ATTRIBUTES = {
    "request_id", "stage", "outcome", "provider", "model", "http.route",
    "http.method", "http.request.method", "gen_ai.system", "gen_ai.provider.name",
    "gen_ai.request.model", "gen_ai.response.model", "gen_ai.operation.name",
}
NUMBER_ATTRIBUTES = {
    "row_count", "regenerations", "provider_attempts", "provider_attempt", "provider_count",
    "duration_ms", "http.status_code", "http.response.status_code",
    "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_creation.input_tokens", "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.aggregated_usage.input_tokens", "gen_ai.aggregated_usage.output_tokens",
    "gen_ai.aggregated_usage.cache_creation.input_tokens",
    "gen_ai.aggregated_usage.cache_read.input_tokens",
}
BOOL_ATTRIBUTES = {"cache_hit", "truncated"}
STAGES = {"pipeline", "C1", "C2", "C4.1", "C4.2", "C4.3", "C4.4", "C5", "C6", "C7",
          "provider", "sql_flow", "synthesis_flow", "entities", "metadata"}


CACHE_REASONS = {"hit", "not_found_or_expired", "payload_invalid", "redis_error", "plan_mismatch", "unsupported_plan", "cache_disabled", "session_missing", "memory_unavailable", "context_changed", "intent_changed"}
CACHE_PHASES = {"pre_sql", "post_sql"}


def safe_attributes(attributes):
    return {
        key: value for key, value in attributes.items()
        if ((key in TEXT_ATTRIBUTES and isinstance(value, str))
            or (key in NUMBER_ATTRIBUTES and type(value) in (int, float))
            or (key in BOOL_ATTRIBUTES and type(value) is bool)
            or (key == "cache_reason" and isinstance(value, str) and value in CACHE_REASONS)
            or (key == "cache_phase" and isinstance(value, str) and value in CACHE_PHASES))
            or (key == "intent_kind" and isinstance(value, str) and value in {"conceptual", "platform", "analytical", "hybrid", "clarification", "unsupported"})
    }


def sanitize_span(span):
    attributes = safe_attributes(span.attributes or {})
    if span.name.startswith("agent.") and span.name[6:] in STAGES:
        name = span.name
    elif "http.request.method" in attributes or "http.method" in attributes:
        method = attributes.get("http.request.method", attributes.get("http.method"))
        name = f"{method} {attributes.get('http.route', 'HTTP request')}"
    else:
        # Nomes de spans automáticos também podem conter conteúdo dinâmico.
        name = "pydantic_ai.operation"
    attributes.update({"logfire.msg": name, "logfire.msg_template": name,
                       "logfire.span_type": "span"})
    return ReadableSpan(
        name=name, context=span.context, parent=span.parent, kind=span.kind,
        start_time=span.start_time, end_time=span.end_time,
        attributes=attributes, events=(), links=(),
        status=Status(span.status.status_code),
        resource=Resource({key: value for key, value in span.resource.attributes.items()
                           if key == "service.name"}),
        instrumentation_scope=(
            InstrumentationScope(span.instrumentation_scope.name, span.instrumentation_scope.version)
            if span.instrumentation_scope is not None else None
        ),
    )


class SafeSpanExporter(SpanExporter):
    def __init__(self, exporter):
        self.exporter = exporter

    def export(self, spans):
        try:
            # Falha de sanitização descarta o lote; nunca exportar o original.
            return self.exporter.export(tuple(sanitize_span(span) for span in spans))
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        try:
            self.exporter.shutdown()
        except Exception:
            pass

    def force_flush(self, timeout_millis=30000):
        try:
            return self.exporter.force_flush(timeout_millis)
        except Exception:
            return False


def create_exporter(settings):
    import logfire
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    base_url = logfire.AdvancedOptions(base_url=settings.logfire_base_url).generate_base_url(
        settings.logfire_token
    )
    return OTLPSpanExporter(
        endpoint=base_url.rstrip("/") + "/v1/traces",
        headers={"Authorization": settings.logfire_token}, timeout=2,
    )
