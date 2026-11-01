"""Contratos da C3 sem rede, credenciais reais ou dados da Gold."""

import asyncio
import logging
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from filelock import FileLock
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.agent.providers import gemini, openrouter, router, usage_store
from app.agent.providers.data_policy import RESTRICTED_MODELS, allows_model
from app.agent.schemas import ProviderAttempt, ProviderErrorType as E, ProviderName
from app.core.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def local_settings(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        gemini_model="primary", gemini_last_resort_model="last",
        openrouter_models=("first", "second"),
        gemini_api_key="synthetic-key", openrouter_api_key="synthetic-key",
        provider_timeout_seconds=20.0, provider_payload_policy="confidential",
    )
    for module in (gemini, openrouter, router):
        monkeypatch.setattr(module, "settings", settings)
    monkeypatch.setattr(usage_store, "USAGE_STATE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr(usage_store, "USAGE_LOCK_PATH", tmp_path / "usage.lock")
    return settings


def attempt(error, *, provider=ProviderName.GEMINI, model="model", order=1):
    return ProviderAttempt(
        provider=provider, model=model, attempt=order,
        started_at=datetime.now(timezone.utc), success=error is None,
        error_type=error, latency_ms=1,
    )


def install_chain(monkeypatch, errors):
    calls = []
    async def run(provider, model, order):
        calls.append((provider, model))
        error = errors[len(calls) - 1]
        return ("ok" if error is None else None,
                attempt(error, provider=provider, model=model, order=order))
    async def google(prompt, *, attempt=1, model_name=None, **kwargs):
        return await run(ProviderName.GEMINI, model_name or "primary", attempt)
    async def fallback(model_name, prompt, *, attempt=1, **kwargs):
        return await run(ProviderName.OPENROUTER, model_name, attempt)
    monkeypatch.setattr(router, "run_gemini", google)
    monkeypatch.setattr(router, "run_openrouter", fallback)
    return calls


@pytest.mark.parametrize(("errors", "expected"), [
    ([E.TIMEOUT, E.TIMEOUT, E.TIMEOUT, E.UNAUTHORIZED], E.UNAUTHORIZED),
    ([E.TIMEOUT, E.QUOTA_EXHAUSTED, E.CONNECTION_ERROR], E.QUOTA_EXHAUSTED),
    ([E.QUOTA_EXHAUSTED, E.TIMEOUT, E.INVALID_OUTPUT, E.FORBIDDEN], E.QUOTA_EXHAUSTED),
    ([E.TIMEOUT, E.BAD_REQUEST], E.BAD_REQUEST),
    ([E.QUOTA_EXHAUSTED, E.UNKNOWN], E.UNKNOWN),
    ([E.TIMEOUT, E.RATE_LIMITED, E.INVALID_OUTPUT, E.TIMEOUT], E.TIMEOUT),
])
@pytest.mark.anyio
async def test_final_error_uses_the_whole_chain(monkeypatch, local_settings, errors, expected):
    calls = install_chain(monkeypatch, errors)
    output, attempts, error = await router.run_with_fallback("synthetic")
    assert output is None
    assert error == expected
    assert len(attempts) == len(errors) == len(calls)
    assert [a.error_type for a in attempts] == errors


@pytest.mark.parametrize("credential_error", [E.UNAUTHORIZED, E.FORBIDDEN, E.CONFIGURATION_ERROR])
@pytest.mark.anyio
async def test_gemini_bad_credentials_allow_independent_provider(
    monkeypatch, local_settings, credential_error,
):
    calls = install_chain(monkeypatch, [credential_error, None])
    output, attempts, error = await router.run_with_fallback("synthetic")
    assert output == "ok" and error is None
    assert [provider for provider, _ in calls] == [ProviderName.GEMINI, ProviderName.OPENROUTER]


@pytest.mark.parametrize("credential_error", [E.UNAUTHORIZED, E.FORBIDDEN, E.CONFIGURATION_ERROR])
@pytest.mark.anyio
async def test_openrouter_bad_credentials_skip_pool_but_allow_gemini(
    monkeypatch, local_settings, credential_error,
):
    calls = install_chain(monkeypatch, [E.TIMEOUT, credential_error, None])
    output, attempts, error = await router.run_with_fallback("synthetic")
    assert output == "ok" and error is None
    assert [model for _, model in calls] == ["primary", "first", "last"]


@pytest.mark.anyio
async def test_invalid_gemini_credentials_are_not_retried_after_pool(monkeypatch, local_settings):
    calls = install_chain(monkeypatch, [E.UNAUTHORIZED, E.TIMEOUT, E.TIMEOUT])
    await router.run_with_fallback("synthetic")
    assert [model for _, model in calls] == ["primary", "first", "second"]


@pytest.mark.anyio
async def test_timeout_then_success(monkeypatch, local_settings):
    install_chain(monkeypatch, [E.TIMEOUT, None])
    output, attempts, error = await router.run_with_fallback("synthetic")
    assert output == "ok" and error is None
    assert len(attempts) == 2


@pytest.mark.anyio
async def test_chain_is_bounded_and_does_not_repeat_models(monkeypatch, local_settings):
    local_settings.openrouter_models = ("first", "first", "second")
    calls = install_chain(monkeypatch, [E.TIMEOUT] * 4)
    _, attempts, error = await router.run_with_fallback("synthetic")
    assert len(calls) == len(attempts) == 4
    assert len(set(calls)) == 4
    assert [a.attempt for a in attempts] == [1, 2, 3, 4]


class StructuredResult(BaseModel):
    value: int


def local_model(text, calls=None):
    def respond(messages, info):
        if calls is not None:
            calls.append(True)
        return ModelResponse(parts=[TextPart(text)])
    return FunctionModel(respond)


@pytest.mark.parametrize("module", [gemini, openrouter])
@pytest.mark.parametrize("text", ["texto livre", '{"value":"incompativel"}'])
@pytest.mark.anyio
async def test_real_agent_rejects_invalid_structured_output(monkeypatch, local_settings, module, text):
    monkeypatch.setattr(module, "_build_model", lambda *args: local_model(text))
    if module is gemini:
        output, result = await gemini.run_gemini("synthetic", output_type=StructuredResult)
    else:
        output, result = await openrouter.run_openrouter("first", "synthetic", output_type=StructuredResult)
    assert output is None
    assert result.error_type == E.INVALID_OUTPUT


@pytest.mark.anyio
async def test_real_validation_triggers_fallback(monkeypatch, local_settings):
    monkeypatch.setattr(gemini, "_build_model", lambda *args: local_model("texto livre"))
    monkeypatch.setattr(openrouter, "_build_model", lambda *args: local_model('{"value":1}'))
    output, attempts, error = await router.run_with_fallback("synthetic", output_type=StructuredResult)
    assert output == StructuredResult(value=1) and error is None
    assert [a.error_type for a in attempts] == [E.INVALID_OUTPUT, None]


@pytest.mark.parametrize("module", [gemini, openrouter])
@pytest.mark.anyio
async def test_real_agent_enforces_model_timeout_without_retry(monkeypatch, local_settings, module):
    calls = []
    async def never_finishes(messages, info):
        calls.append(True)
        await asyncio.Event().wait()
    local_settings.provider_timeout_seconds = 0.02
    monkeypatch.setattr(module, "_build_model", lambda *args: FunctionModel(never_finishes))
    if module is gemini:
        output, result = await asyncio.wait_for(gemini.run_gemini("synthetic"), 1)
    else:
        output, result = await asyncio.wait_for(openrouter.run_openrouter("first", "synthetic"), 1)
    assert output is None and result.error_type == E.TIMEOUT
    assert calls == [True]


@pytest.mark.anyio
async def test_corrupted_store_is_only_lost_telemetry(monkeypatch, local_settings):
    usage_store.USAGE_STATE_PATH.write_text("{invalid JSON", encoding="utf-8")
    monkeypatch.setattr(openrouter, "_build_model", lambda *args: local_model("ok"))
    output, result = await openrouter.run_openrouter("first", "synthetic")
    assert output == "ok" and result.success


@pytest.mark.parametrize("failure", ["mkdir", "read", "write", "lock"])
@pytest.mark.anyio
async def test_store_failure_does_not_prevent_provider(monkeypatch, local_settings, failure, caplog):
    def fail(*args, **kwargs):
        raise OSError("SENSITIVE_STORE_CONTENT")
    calls = []
    monkeypatch.setattr(openrouter, "_build_model", lambda *args: local_model("ok", calls))
    lock = None
    if failure == "lock":
        lock = FileLock(str(usage_store.USAGE_LOCK_PATH))
        lock.acquire()
    else:
        target = {"mkdir": "_ensure_runtime_directory", "read": "_load_state", "write": "_save_state"}[failure]
        monkeypatch.setattr(usage_store, target, fail)
    try:
        with caplog.at_level(logging.WARNING):
            output, result = await asyncio.wait_for(openrouter.run_openrouter("first", "synthetic"), 2)
        assert result.success and output == "ok" and calls == [True]
        assert "SENSITIVE_STORE_CONTENT" not in caplog.text
        assert caplog.records
        assert all(record.exc_info is None for record in caplog.records)
    finally:
        if lock is not None:
            lock.release()


@pytest.mark.anyio
async def test_slow_store_does_not_block_event_loop_or_queue_unbounded_work(monkeypatch, local_settings):
    started, release, finished = Event(), Event(), Event()
    calls = []
    def slow_store():
        started.set()
        try:
            release.wait(2)
        finally:
            finished.set()
    monkeypatch.setattr(openrouter, "register_request_attempt", slow_store)
    monkeypatch.setattr(usage_store, "RECORD_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(openrouter, "_build_model", lambda *args: local_model("ok", calls))
    try:
        output, result = await asyncio.wait_for(openrouter.run_openrouter("first", "synthetic"), 1)
        assert started.is_set() and not finished.is_set()
        assert output == "ok" and result.success
        skipped = Mock()
        await usage_store.record_attempt_best_effort(skipped)
        skipped.assert_not_called()
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 2)


@pytest.mark.parametrize("module", [gemini, openrouter])
@pytest.mark.anyio
async def test_logs_contain_only_safe_metadata(monkeypatch, local_settings, module, caplog):
    def fail(messages, info):
        try:
            raise ValueError("SECRET_CAUSE")
        except ValueError as cause:
            raise RuntimeError("SECRET_PROMPT_BODY") from cause
    monkeypatch.setattr(module, "_build_model", lambda *args: FunctionModel(fail))
    with caplog.at_level(logging.WARNING):
        if module is gemini:
            _, result = await gemini.run_gemini("synthetic")
        else:
            _, result = await openrouter.run_openrouter("first", "synthetic")
    assert result.error_type == E.UNKNOWN
    assert "SECRET_" not in caplog.text and "Traceback" not in caplog.text
    assert "category=unknown" in caplog.text and "exception_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("policy", ["confidential", "", "invalid", "synthetic"])
def test_restricted_model_is_fail_safe(policy):
    model = next(iter(RESTRICTED_MODELS))
    assert allows_model(model, policy) is (policy == "synthetic")
    assert allows_model("cohere/north-mini-code:free", policy)


def test_settings_default_to_confidential_and_twenty_seconds(monkeypatch):
    monkeypatch.delenv("PROVIDER_PAYLOAD_POLICY", raising=False)
    assert Settings().provider_payload_policy == "confidential"
    assert Settings().provider_timeout_seconds == 20
    monkeypatch.setenv("PROVIDER_PAYLOAD_POLICY", "synthetic")
    assert Settings().provider_payload_policy == "synthetic"


@pytest.mark.anyio
async def test_direct_adapter_cannot_bypass_data_policy(monkeypatch, local_settings):
    build = Mock(side_effect=AssertionError("não deve criar modelo"))
    monkeypatch.setattr(openrouter, "_build_model", build)
    output, result = await openrouter.run_openrouter(next(iter(RESTRICTED_MODELS)), "synthetic")
    assert output is None and result.error_type == E.CONFIGURATION_ERROR
    build.assert_not_called()


@pytest.mark.parametrize("policy", ["confidential", "synthetic"])
@pytest.mark.anyio
async def test_router_filters_restricted_model_without_replacing_it(monkeypatch, local_settings, policy):
    restricted = next(iter(RESTRICTED_MODELS))
    local_settings.openrouter_models = ("first", restricted)
    local_settings.provider_payload_policy = policy
    calls = install_chain(monkeypatch, [E.TIMEOUT] * 4)
    await router.run_with_fallback("synthetic")
    assert (restricted in [model for _, model in calls]) is (policy == "synthetic")
    assert [model for _, model in calls] == (
        ["primary", "first", restricted, "last"] if policy == "synthetic"
        else ["primary", "first", "last"]
    )
