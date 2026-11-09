"""Comparações determinísticas, sem rede nem conteúdo real."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.agent.providers import latency_policy as policy, router
from app.agent.schemas import (
    ProviderAttempt, ProviderErrorType as E, ProviderName as P,
    SQLGenerationResult, SynthesisResult,
)
from app.core.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def config(monkeypatch):
    config = SimpleNamespace(
        gemini_model="primary", gemini_last_resort_model="last",
        openrouter_models=("fallback",), provider_payload_policy="confidential",
        provider_timeout_seconds=20., provider_primary_timeout_seconds=8.,
        provider_reuse_success=True, provider_phase_budgets_enabled=False,
        provider_sql_budget_seconds=30., provider_synthesis_budget_seconds=20.,
    )
    monkeypatch.setattr(router, "settings", config)
    monkeypatch.setattr(policy, "settings", config)
    return config


@pytest.fixture
def clock(monkeypatch):
    now = [0.]
    monkeypatch.setattr(router, "monotonic", lambda: now[0])
    monkeypatch.setattr(policy, "monotonic", lambda: now[0])
    return now


def install(monkeypatch, clock, durations, errors=None):
    calls = []
    async def run(provider, model, order):
        timeout = policy.attempt_timeout.get()
        calls.append((provider, model, timeout))
        duration = durations.get(model, 1.)
        elapsed = min(timeout, duration)
        clock[0] += elapsed
        error = E.TIMEOUT if duration > timeout else (errors or {}).get(model)
        return (None if error else "ok", ProviderAttempt(
            provider=provider, model=model, attempt=order,
            started_at=datetime.now(timezone.utc), success=error is None,
            latency_ms=elapsed * 1000, error_type=error,
        ))
    async def gemini(prompt, *, attempt=1, model_name=None, **kwargs):
        return await run(P.GEMINI, model_name or "primary", attempt)
    async def openrouter(model, prompt, *, attempt=1, **kwargs):
        return await run(P.OPENROUTER, model, attempt)
    monkeypatch.setattr(router, "run_gemini", gemini)
    monkeypatch.setattr(router, "run_openrouter", openrouter)
    return calls


@pytest.mark.anyio
async def test_primary_timeout_fallback_and_reuse(monkeypatch, config, clock):
    calls = install(monkeypatch, clock, {"primary": 25., "fallback": 2.})
    with policy.request_scope():
        _, attempts, error = await router.run_with_fallback("synthetic", output_type=SQLGenerationResult)
        assert error is None and attempts[0].error_type == E.TIMEOUT
        await router.run_with_fallback("synthetic", output_type=SynthesisResult)
    assert [(m, t) for _, m, t in calls] == [("primary", 8.), ("fallback", 20.), ("fallback", 20.)]
    assert policy.request_policy.get() is None
    assert policy.attempt_timeout.get() is None


@pytest.mark.anyio
async def test_preferred_failure_returns_to_normal_chain_without_duplicates(monkeypatch, config, clock):
    calls = install(monkeypatch, clock, {}, {"fallback": E.TIMEOUT})
    with policy.request_scope() as state:
        state.preferred = (P.OPENROUTER, "fallback")
        _, attempts, error = await router.run_with_fallback("synthetic")
    assert error is None
    assert [m for _, m, _ in calls] == ["fallback", "primary"]
    assert [a.attempt for a in attempts] == [1, 2]
    assert all(t == 20 for _, _, t in calls)


@pytest.mark.anyio
async def test_incompatible_output_does_not_promote_preferred(monkeypatch, config, clock):
    calls = install(monkeypatch, clock, {})
    with policy.request_scope() as state:
        state.preferred = (P.OPENROUTER, "fallback")
        await router.run_with_fallback("synthetic", output_type=int)
    assert calls[0][1] == "primary"


@pytest.mark.anyio
async def test_privacy_rechecked_before_preference(monkeypatch, config, clock):
    restricted = "nvidia/nemotron-3-ultra-550b-a55b:free"
    config.openrouter_models = (restricted, "fallback")
    calls = install(monkeypatch, clock, {})
    with policy.request_scope() as state:
        state.preferred = (P.OPENROUTER, restricted)
        await router.run_with_fallback("synthetic")
    assert all(m != restricted for _, m, _ in calls)


@pytest.mark.anyio
async def test_budget_shared_across_rounds(monkeypatch, config, clock):
    config.provider_phase_budgets_enabled = True
    config.provider_sql_budget_seconds = 8.
    calls = install(monkeypatch, clock, {"primary": 5.})
    @policy.provider_phase("sql")
    async def phase():
        assert (await router.run_with_fallback("synthetic"))[2] is None
        return await router.run_with_fallback("synthetic")
    with policy.request_scope():
        _, attempts, error = await phase()
    assert error == E.TIMEOUT
    assert len(attempts) == 1
    assert [t for _, _, t in calls] == [8., 3.]
    assert clock[0] == 8.
    assert policy.phase_deadline.get() is None


@pytest.mark.anyio
async def test_no_call_when_budget_already_exhausted(monkeypatch, config, clock):
    calls = install(monkeypatch, clock, {})
    token = policy.phase_deadline.set(0.)
    try:
        output, attempts, error = await router.run_with_fallback("synthetic")
    finally:
        policy.phase_deadline.reset(token)
    assert output is None and attempts == [] and error == E.TIMEOUT and calls == []


@pytest.mark.anyio
async def test_disabled_budget_allows_regeneration_time(monkeypatch, config, clock):
    calls = install(monkeypatch, clock, {"primary": 7.})
    config.provider_sql_budget_seconds = 1.
    @policy.provider_phase("sql")
    async def phase():
        for _ in range(2):
            assert (await router.run_with_fallback("synthetic"))[2] is None
    await phase()
    assert len(calls) == 2 and clock[0] == 14.


@pytest.mark.anyio
async def test_timeout_waits_for_cleanup_and_leaves_no_tasks(monkeypatch, config):
    config.provider_primary_timeout_seconds = .01
    finished = []
    async def primary(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(True)
    async def fallback(model, *args, **kwargs):
        assert finished == [True]
        return "ok", ProviderAttempt(
            provider=P.OPENROUTER, model=model, attempt=2,
            started_at=datetime.now(timezone.utc), success=True,
        )
    monkeypatch.setattr(router, "run_gemini", primary)
    monkeypatch.setattr(router, "run_openrouter", fallback)
    before = asyncio.all_tasks()
    assert (await router.run_with_fallback("synthetic"))[2] is None
    assert asyncio.all_tasks() == before
    assert policy.attempt_timeout.get() is None


@pytest.mark.anyio
async def test_request_context_isolated_during_concurrent_requests():
    ready = asyncio.Event()
    @policy.provider_request
    async def first():
        policy.request_policy.get().preferred = (P.OPENROUTER, "fallback")
        ready.set()
        await asyncio.sleep(0)
        return policy.request_policy.get().preferred
    @policy.provider_request
    async def second():
        await ready.wait()
        assert policy.request_policy.get().preferred is None
    await asyncio.gather(first(), second())
    assert policy.request_policy.get() is None


@pytest.mark.anyio
async def test_request_cleanup_after_cancellation():
    @policy.provider_request
    async def request():
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await request()
    assert policy.request_policy.get() is None


@pytest.mark.anyio
async def test_synthetic_ab_comparison(monkeypatch, config, clock):
    # Mesmo cenário artificial: principal lento, fallback rápido, SQL e síntese.
    results = []
    for timeout, reuse in [(20., False), (8., True)]:
        config.provider_primary_timeout_seconds = timeout
        config.provider_reuse_success = reuse
        clock[0] = 0.
        calls = install(monkeypatch, clock, {"primary": 25., "fallback": 2.})
        with policy.request_scope():
            outputs = [await router.run_with_fallback("synthetic") for _ in range(2)]
        results.append((clock[0], sum(e is None for _, _, e in outputs), len(calls)))
    assert results == [(44., 2, 4), (12., 2, 3)]


@pytest.mark.anyio
async def test_short_timeout_can_lose_a_valid_response(monkeypatch, config, clock):
    successes = []
    for timeout in (20., 8.):
        config.provider_primary_timeout_seconds = timeout
        install(monkeypatch, clock, {"primary": 15., "fallback": 25., "last": 25.})
        successes.append((await router.run_with_fallback("synthetic"))[2] is None)
    assert successes == [True, False]


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_invalid_timeout_configuration_rejected(monkeypatch, value):
    monkeypatch.setenv("PROVIDER_PRIMARY_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="positivo e finito"):
        Settings()


def test_policy_defaults_and_rollback(monkeypatch):
    for name in ("PROVIDER_PRIMARY_TIMEOUT_SECONDS", "PROVIDER_PHASE_BUDGETS_ENABLED", "PROVIDER_REUSE_SUCCESS"):
        monkeypatch.delenv(name, raising=False)
    config = Settings()
    assert config.provider_primary_timeout_seconds == 8
    assert config.provider_phase_budgets_enabled
    assert config.provider_sql_budget_seconds == 30
    assert config.provider_synthesis_budget_seconds == 20
    monkeypatch.setenv("PROVIDER_PRIMARY_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("PROVIDER_REUSE_SUCCESS", "false")
    monkeypatch.setenv("PROVIDER_PHASE_BUDGETS_ENABLED", "false")
    config = Settings()
    assert config.provider_primary_timeout_seconds == 20 and not config.provider_reuse_success
    assert not config.provider_phase_budgets_enabled


@pytest.mark.anyio
async def test_c5_regeneration_shares_synthesis_budget(monkeypatch, config, clock):
    from app.agent import synthesis_orchestrator as synthesis
    from app.agent.schemas import QueryExecutionResult, SynthesisStatus
    config.provider_phase_budgets_enabled = True
    config.provider_synthesis_budget_seconds = 8.
    calls = install(monkeypatch, clock, {"primary": 5.})
    async def synthesize(**kwargs):
        _, attempts, error = await router.run_with_fallback("synthetic", output_type=SynthesisResult)
        if error:
            return None, attempts, error
        return SynthesisResult(status=SynthesisStatus.ANSWERED, answer="Há 999 unidades."), attempts, None
    monkeypatch.setattr(synthesis, "synthesize_answer", synthesize)
    with policy.request_scope():
        flow = await synthesis.synthesize_and_validate(
            "Quantas unidades?", "SELECT quantidade FROM resumo",
            QueryExecutionResult(columns=["quantidade"], rows=[[7]], row_count=1),
        )
    assert flow.regenerations == 1 and not flow.approved
    assert flow.provider_error == E.TIMEOUT
    assert [t for _, _, t in calls] == [8., 3.]
    assert synthesis.MAX_OUTPUT_REGENERATIONS == 1


@pytest.mark.anyio
async def test_no_content_in_policy_or_timeout_telemetry(monkeypatch, config, clock, caplog):
    calls = install(monkeypatch, clock, {"primary": 25.})
    secret = "synthetic-secret-never-export"
    with policy.request_scope() as state:
        _, attempts, _ = await router.run_with_fallback(secret, instructions=secret)
        assert secret not in repr(state)
        assert secret not in str([a.model_dump() for a in attempts])
    assert secret not in caplog.text
    assert len(calls) == 2


@pytest.mark.parametrize("adapter_name", ["gemini", "openrouter"])
@pytest.mark.anyio
async def test_attempt_timeout_reaches_real_agent_without_extra_retries(monkeypatch, config, adapter_name):
    from app.agent.providers import gemini, openrouter
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, TextPart
    adapter = gemini if adapter_name == "gemini" else openrouter
    config.gemini_api_key = config.openrouter_api_key = "synthetic-key"
    monkeypatch.setattr(adapter, "settings", config)
    seen = []
    def respond(messages, info):
        seen.append(info.model_settings)
        return ModelResponse(parts=[TextPart("ok")])
    monkeypatch.setattr(adapter, "_build_model", lambda *args: FunctionModel(respond))
    if adapter_name == "openrouter":
        async def no_io(*args):
            pass
        monkeypatch.setattr(adapter, "record_attempt_best_effort", no_io)
    token = policy.attempt_timeout.set(8.)
    try:
        if adapter_name == "gemini":
            output, attempt = await adapter.run_gemini("synthetic")
        else:
            output, attempt = await adapter.run_openrouter("fallback", "synthetic")
    finally:
        policy.attempt_timeout.reset(token)
    assert output == "ok" and attempt.success
    assert len(seen) == 1
    assert seen[0]["request_timeout"] == 8.
    assert seen[0]["max_retries"] == 0
