"""Telemetria real com exportador em memória, sem chamadas externas."""

import asyncio
from dataclasses import replace
import json
import sqlite3
import subprocess
import sys
from unittest.mock import Mock

import logfire
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.util.instrumentation import InstrumentationScope
from opentelemetry.trace import Status, StatusCode
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.agent import pipeline, sql_executor
from app.agent.providers import gemini
from app.agent.schemas import AgentOutcome, AuditRecord
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.finalizer import finalize
from app.core.config import settings
from app.core import observability as obs
from app.core import telemetry_export
from app.routers import ia


@pytest.fixture(autouse=True)
def block_real_model_requests(monkeypatch):
    from pydantic_ai import models

    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)


def _app():
    app = FastAPI()
    app.include_router(ia.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/error")
    def error():
        raise RuntimeError("EXCEPTION_PRIVATE_CONTENT")

    return app


@pytest.fixture
def telemetry(monkeypatch):
    exporter = InMemorySpanExporter()
    originals = []
    export = telemetry_export.SafeSpanExporter.export

    def capture(self, batch):
        originals.extend(batch)
        return export(self, batch)

    monkeypatch.setattr(telemetry_export.SafeSpanExporter, "export", capture)
    monkeypatch.setattr(telemetry_export, "create_exporter", lambda _: exporter)
    monkeypatch.setattr(obs, "_logfire", None)
    previous = Agent._instrument_default
    config = replace(settings, logfire_enabled=True, logfire_token="TEST_WRITE_TOKEN")
    app = _app()
    configured = obs.configure_observability(app, config)
    assert configured
    client = obs._logfire

    def spans():
        assert client.force_flush()
        return exporter.get_finished_spans()

    spans.originals = originals

    yield app, client, spans
    Agent.instrument_all(previous)
    client.shutdown()


def _synthetic_pipeline(monkeypatch, tmp_path, *, regenerate=False, truncated=False):
    path = tmp_path / "synthetic.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE dim_uc (municipio TEXT)")
        connection.execute("INSERT INTO dim_uc VALUES ('GOLD_PRIVATE_VALUE')")
    config = replace(settings, gemini_api_key="API_KEY_PRIVATE", sqlite_path=str(path))
    monkeypatch.setattr(gemini, "settings", config)
    monkeypatch.setattr(sql_executor, "settings", config)
    calls = []

    def model(*_args):
        calls.append(None)
        if len(calls) == 1 and regenerate:
            output = {"status": "ready", "sql": "SELECT coluna_inexistente FROM dim_uc"}
        elif len(calls) <= (2 if regenerate else 1):
            output = {"status": "ready", "sql": "SELECT municipio, COUNT(*) AS total FROM dim_uc GROUP BY municipio"}
        else:
            output = {"status": "answered", "answer": "Há 1 unidade consumidora."}
        return TestModel(custom_output_text=json.dumps(output), profile={"supports_json_schema_output": True})

    monkeypatch.setattr(gemini, "_build_model", model)
    monkeypatch.setattr(pipeline, "load_database_context", lambda: "MEMORY_SCHEMA_PRIVATE")
    monkeypatch.setattr(pipeline, "get_state_dependencies", lambda: AgentStateDependencies())
    if truncated:
        from app.agent import sql_execution_orchestrator as execution

        original = execution.execute_sql.__wrapped__

        @obs.observe("C4.3")
        def execute(*args, **kwargs):
            outcome = original(*args, **kwargs)
            outcome.result.truncated = True
            return outcome

        monkeypatch.setattr(execution, "execute_sql", execute)
    return calls


@pytest.mark.parametrize("enabled,token", [(False, None), (False, "token"), (True, None)])
def test_optional_configuration_does_not_load_sdk(monkeypatch, enabled, token):
    configure = Mock(side_effect=AssertionError("SDK não deve ser chamado"))
    monkeypatch.setattr(logfire, "configure", configure)
    app = _app()
    assert not obs.configure_observability(
        app, replace(settings, logfire_enabled=enabled, logfire_token=token)
    )
    assert TestClient(app).get("/health").json() == {"status": "ok"}
    configure.assert_not_called()


def test_http_to_pipeline_is_correlated_and_contains_only_metadata(telemetry, monkeypatch, tmp_path):
    app, _, spans = telemetry
    _synthetic_pipeline(monkeypatch, tmp_path)
    response = TestClient(app).post(
        "/api/ia/perguntar?secret=QUERY_PRIVATE",
        json={"pergunta": "Quantas UCs por município?", "sessao_id": "SESSION_PRIVATE"},
        headers={"Authorization": "Bearer HEADER_PRIVATE"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    exported = spans()
    stages = {item.name for item in exported}
    assert {"agent.pipeline", "agent.C1", "agent.C2", "agent.C4.1", "agent.C4.2",
            "agent.C4.3", "agent.C4.4", "agent.C5", "agent.C6", "agent.provider"} <= stages
    root = next(item for item in exported if item.name == "POST /api/ia/perguntar")
    flow = next(item for item in exported if item.name == "agent.pipeline")
    assert flow.parent.span_id == root.context.span_id
    assert all(item.context.trace_id == root.context.trace_id for item in exported)
    assert root.attributes["request_id"] == flow.attributes["request_id"]
    assert flow.attributes["outcome"] == "answered"
    assert flow.attributes["row_count"] == 1
    assert flow.attributes["truncated"] is False
    assert flow.attributes["cache_hit"] is False
    assert flow.attributes["provider_attempts"] == 2
    assert flow.attributes["provider_count"] == 1
    assert flow.attributes["c7_persistence_connected"] is False
    assert "agent.C7" not in stages
    assert all(item.attributes["duration_ms"] >= 0 for item in exported if item.name.startswith("agent."))
    serialized = json.dumps([item.to_json() for item in exported])
    original_stage_attributes = [dict(item.attributes) for item in spans.originals
                                 if item.name.startswith("agent.")]
    assert original_stage_attributes
    for secret in ("Quantas UCs", "Há 1 unidade", "SELECT municipio", "GOLD_PRIVATE_VALUE",
                   "MEMORY_SCHEMA_PRIVATE", "SESSION_PRIVATE", "API_KEY_PRIVATE",
                   "QUERY_PRIVATE", "HEADER_PRIVATE"):
        assert secret not in serialized
        assert secret not in json.dumps(original_stage_attributes)
    assert any("gen_ai.usage.input_tokens" in item.attributes for item in exported)


@pytest.mark.parametrize("regenerate,truncated", [(False, False), (True, False), (False, True)])
def test_pipeline_result_is_identical_with_and_without_telemetry(
    telemetry, monkeypatch, tmp_path, regenerate, truncated,
):
    _, client, spans = telemetry
    calls = _synthetic_pipeline(monkeypatch, tmp_path, regenerate=regenerate, truncated=truncated)

    def run():
        return asyncio.run(pipeline.answer_question(
            "Quantas UCs por município?", session_id="SESSION_PRIVATE",
            memory_context="MEMORY_PRIVATE", state_dependencies=AgentStateDependencies(),
        ))

    observed = run()
    calls.clear()
    monkeypatch.setattr(obs, "_logfire", None)
    Agent.instrument_all(False)
    baseline = run()
    assert replace(observed, request_id=baseline.request_id, provider_attempts=()) == replace(
        baseline, provider_attempts=()
    )
    assert [(a.provider, a.model, a.success, a.error_type) for a in observed.provider_attempts] == [
        (a.provider, a.model, a.success, a.error_type) for a in baseline.provider_attempts
    ]
    flow = next(item for item in spans() if item.name == "agent.pipeline")
    assert flow.attributes["regenerations"] == int(regenerate)
    assert flow.attributes["provider_attempts"] == (3 if regenerate else 2)
    assert flow.attributes["truncated"] == truncated


def test_cache_hit_skips_model_stages(telemetry, monkeypatch):
    from app.agent.schemas import PostProcessingResult
    from app.agent.state.request_state import MemoryContextStatus, RequestState

    _, _, spans = telemetry
    cached = PostProcessingResult(answer="CACHE_PRIVATE", assumptions=[])

    @obs.observe("C2")
    async def prepare(**_kwargs):
        return RequestState(None, None, MemoryContextStatus.EMPTY, cached)

    monkeypatch.setattr(pipeline, "prepare_request_state", prepare)
    monkeypatch.setattr(pipeline, "get_state_dependencies", lambda: AgentStateDependencies())
    result = asyncio.run(pipeline.answer_question("Quantas UCs?"))
    assert result.cache_hit
    exported = spans()
    assert next(s for s in exported if s.name == "agent.C2").attributes["cache_hit"] is True
    root = next(s for s in exported if s.name == "agent.pipeline")
    assert root.attributes["provider_attempts"] == 0
    assert root.attributes["outcome"] == "answered"
    assert "agent.C4.1" not in {s.name for s in exported}


def test_c7_records_metadata_without_audit_content(telemetry):
    from unittest.mock import AsyncMock

    _, _, spans = telemetry
    record = AuditRecord(request_id="generated-request-id", question="QUESTION_PRIVATE",
                         session_id="SESSION_PRIVATE", final_answer="ANSWER_PRIVATE",
                         sql="SQL_PRIVATE", outcome=AgentOutcome.ANSWERED, row_count=4,
                         truncated=True, regenerations=1)
    asyncio.run(finalize(audit_store=Mock(save=AsyncMock()), audit_record=record))
    item = next(s for s in spans() if s.name == "agent.C7")
    assert item.attributes["outcome"] == "answered"
    assert item.attributes["row_count"] == 4
    assert item.attributes["truncated"] is True
    assert "PRIVATE" not in item.to_json()


@pytest.mark.parametrize("failure", ["configure", "instrument_fastapi", "instrument_pydantic_ai"])
def test_initialization_failure_keeps_http_and_pipeline_working(monkeypatch, failure):
    monkeypatch.setattr(telemetry_export, "create_exporter", lambda _: InMemorySpanExporter())
    target = logfire if failure == "configure" else logfire.Logfire
    monkeypatch.setattr(target, failure, Mock(side_effect=RuntimeError("TOKEN_PRIVATE")))
    app = _app()
    assert not obs.configure_observability(
        app, replace(settings, logfire_enabled=True, logfire_token="TOKEN_PRIVATE")
    )
    assert TestClient(app).get("/health").status_code == 200
    assert asyncio.run(pipeline.answer_question("" )).status == pipeline.PipelineStatus.NO_ANSWER


def test_export_sanitizes_names_errors_resources_and_content():
    memory = InMemorySpanExporter()
    exporter = telemetry_export.SafeSpanExporter(memory)
    original = ReadableSpan(
        name="GET /SESSION_PRIVATE?question=QUESTION_PRIVATE",
        attributes={"http.method": "GET", "http.route": "/api/ia/sessoes/{sessao_id}",
                    "http.url": "URL_PRIVATE", "fastapi.arguments.values": "BODY_PRIVATE",
                    "gen_ai.input.messages": "PROMPT_PRIVATE", "row_count": 4,
                    "gen_ai.usage.input_tokens": 10},
        events=[Event("exception", attributes={"exception.message": "EXCEPTION_PRIVATE"})],
        status=Status(StatusCode.ERROR, "STATUS_PRIVATE"),
        resource=Resource({"service.name": "backend", "process.command_args": "KEY_PRIVATE"}),
        instrumentation_scope=InstrumentationScope("test", attributes={"api_key": "SCOPE_PRIVATE"}),
    )
    assert exporter.export([original]) == SpanExportResult.SUCCESS
    safe = memory.get_finished_spans()[0]
    assert safe.name == "GET /api/ia/sessoes/{sessao_id}"
    assert safe.attributes["row_count"] == 4
    assert safe.attributes["gen_ai.usage.input_tokens"] == 10
    assert safe.events == ()
    assert safe.status.description is None
    assert not safe.instrumentation_scope.attributes
    assert "PRIVATE" not in safe.to_json()


def test_validation_errors_urls_sessions_and_exceptions_are_not_exported(telemetry):
    app, _, spans = telemetry
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/api/ia/perguntar", json={"pergunta": {"secret": "BODY_PRIVATE"}}).status_code == 422
    assert client.delete("/api/ia/sessoes/SESSION_PRIVATE?q=QUERY_PRIVATE").status_code == 204
    assert client.get("/unknown/UNKNOWN_PRIVATE").status_code == 404
    assert client.get("/error").status_code == 500
    exported = spans()
    assert len(exported) >= 4
    assert "PRIVATE" not in json.dumps([item.to_json() for item in exported])


def test_span_sdk_failure_does_not_change_application_result(monkeypatch):
    broken = Mock(span=Mock(side_effect=RuntimeError("PRIVATE")))
    monkeypatch.setattr(obs, "_logfire", broken)
    result = asyncio.run(pipeline.answer_question(""))
    assert result.stage == pipeline.PipelineStage.INPUT_GUARDRAIL


def test_exporter_failure_is_best_effort(telemetry, monkeypatch):
    _, _, spans = telemetry
    exporter = Mock(export=Mock(side_effect=RuntimeError("PRIVATE")))
    wrapper = telemetry_export.SafeSpanExporter(exporter)
    assert wrapper.export([ReadableSpan("test", resource=Resource({}))]) == SpanExportResult.FAILURE
    exporter.export.assert_called_once()
    result = asyncio.run(pipeline.answer_question(""))
    assert result.stage == pipeline.PipelineStage.INPUT_GUARDRAIL
    assert next(s for s in spans() if s.name == "agent.pipeline").attributes["outcome"] == "input_blocked"


@pytest.mark.parametrize("failure", ["enter", "set", "exit"])
def test_span_lifecycle_failure_preserves_results_and_application_exceptions(monkeypatch, failure):
    class BrokenSpan:
        def __enter__(self):
            if failure == "enter":
                raise RuntimeError("SDK_PRIVATE")
            return self

        def set_attribute(self, *_args):
            if failure == "set":
                raise RuntimeError("SDK_PRIVATE")

        def __exit__(self, *_args):
            if failure == "exit":
                raise RuntimeError("SDK_PRIVATE")

    monkeypatch.setattr(obs, "_logfire", Mock(span=Mock(return_value=BrokenSpan())))
    assert asyncio.run(pipeline.answer_question("")).status == pipeline.PipelineStatus.NO_ANSWER

    @obs.observe("C6")
    def broken_application():
        raise ValueError("APPLICATION_PRIVATE")

    with pytest.raises(ValueError, match="APPLICATION_PRIVATE"):
        broken_application()


def test_missing_sdk_does_not_prevent_application_startup():
    code = """
import importlib.abc
import os
import sys
os.environ['LOGFIRE_ENABLED'] = 'true'
os.environ['LOGFIRE_TOKEN'] = 'SYNTHETIC'
class MissingLogfire(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'logfire' or fullname.startswith('logfire.'):
            raise ModuleNotFoundError('SDK indisponivel')
sys.meta_path.insert(0, MissingLogfire())
from app.main import app
from fastapi.testclient import TestClient
assert TestClient(app).get('/api/health').status_code == 200
assert not getattr(app.state, 'observability_enabled', False)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def test_external_otlp_exporter_cannot_bypass_filter(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://example.invalid")
    create_exporter = Mock()
    monkeypatch.setattr(telemetry_export, "create_exporter", create_exporter)
    app = _app()
    configured = obs.configure_observability(
        app, replace(settings, logfire_enabled=True, logfire_token="SYNTHETIC")
    )
    assert not configured
    create_exporter.assert_not_called()
    assert TestClient(app).get("/health").status_code == 200
