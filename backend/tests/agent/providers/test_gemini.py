from types import SimpleNamespace

import pytest
from pydantic_ai.exceptions import ModelAPIError

from app.agent.providers import gemini
from app.agent.schemas import (
    ProviderErrorType,
    ProviderName,
)


def test_generic_model_api_error_is_recoverable():
    error = ModelAPIError(
        model_name="gemini-3.1-flash-lite",
        message="Falha genérica simulada do provider.",
    )

    result = gemini.classify_gemini_error(error)

    assert (
        result
        == ProviderErrorType.PROVIDER_UNAVAILABLE
    )
@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_settings(
    api_key: str | None = "fake-key",
):
    return SimpleNamespace(
        gemini_api_key=api_key,
        gemini_model="gemini-3.1-flash-lite",
        provider_timeout_seconds=20.0,
    )


class FakeResult:
    def __init__(self, output):
        self.output = output


class SuccessfulAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def run(
        self,
        prompt,
        *,
        instructions=None,
        output_type=str,
    ):
        return FakeResult(
            "resposta simulada"
        )


class FailingAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def run(
        self,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "falha simulada"
        )


@pytest.mark.anyio
async def test_missing_api_key_returns_configuration_error(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(api_key=None),
    )

    output, attempt = await gemini.run_gemini(
        "teste",
    )

    assert output is None

    assert (
        attempt.provider
        == ProviderName.GEMINI
    )

    assert (
        attempt.model
        == "gemini-3.1-flash-lite"
    )

    assert attempt.attempt == 1
    assert attempt.success is False
    assert attempt.latency_ms == 0.0

    assert (
        attempt.error_type
        == ProviderErrorType.CONFIGURATION_ERROR
    )


@pytest.mark.anyio
async def test_successful_gemini_call(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        lambda: object(),
    )

    output, attempt = await gemini.run_gemini(
        "Qual foi o consumo?",
    )

    assert output == "resposta simulada"

    assert (
        attempt.provider
        == ProviderName.GEMINI
    )

    assert (
        attempt.model
        == "gemini-3.1-flash-lite"
    )

    assert attempt.attempt == 1
    assert attempt.success is True
    assert attempt.error_type is None
    assert attempt.latency_ms is not None
    assert attempt.latency_ms >= 0


@pytest.mark.anyio
async def test_successful_call_preserves_attempt_number(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        lambda: object(),
    )

    output, attempt = await gemini.run_gemini(
        "teste",
        attempt=3,
    )

    assert output == "resposta simulada"
    assert attempt.attempt == 3
    assert attempt.success is True


@pytest.mark.anyio
async def test_failed_gemini_call_returns_unknown_error(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        FailingAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        lambda: object(),
    )

    output, attempt = await gemini.run_gemini(
        "teste",
    )

    assert output is None

    assert (
        attempt.provider
        == ProviderName.GEMINI
    )

    assert attempt.success is False

    assert (
        attempt.error_type
        == ProviderErrorType.UNKNOWN
    )

    assert attempt.latency_ms is not None
    assert attempt.latency_ms >= 0


def test_classify_unknown_error():
    error = RuntimeError(
        "erro qualquer"
    )

    result = gemini.classify_gemini_error(
        error
    )

    assert (
        result
        == ProviderErrorType.UNKNOWN
    )


@pytest.mark.anyio
async def test_instructions_are_passed_to_agent(
    monkeypatch,
):
    captured = {}

    class CapturingAgent:
        def __init__(self, *args, **kwargs):
            pass

        async def run(
            self,
            prompt,
            *,
            instructions=None,
            output_type=str,
        ):
            captured["prompt"] = prompt
            captured["instructions"] = instructions

            return FakeResult(
                "ok"
            )

    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        CapturingAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        lambda: object(),
    )

    output, attempt = await gemini.run_gemini(
        "Pergunta do usuário",
        instructions="Responda apenas com dados.",
    )

    assert output == "ok"

    assert (
        captured["prompt"]
        == "Pergunta do usuário"
    )

    assert (
        captured["instructions"]
        == "Responda apenas com dados."
    )

    assert attempt.success is True


@pytest.mark.anyio
async def test_model_name_is_used_for_the_call_and_the_attempt(
    monkeypatch,
):
    built = []

    def fake_build_model(model_name=None):
        built.append(model_name)

        return object()

    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        fake_build_model,
    )

    output, attempt = await gemini.run_gemini(
        "Qual foi o consumo?",
        model_name="gemini-ultimo-recurso",
    )

    assert output == "resposta simulada"
    assert built == ["gemini-ultimo-recurso"]
    assert attempt.model == "gemini-ultimo-recurso"
    assert attempt.success is True


@pytest.mark.anyio
async def test_default_model_is_built_without_arguments(
    monkeypatch,
):
    built = []

    def fake_build_model(*args):
        built.append(args)

        return object()

    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        fake_build_model,
    )

    _, attempt = await gemini.run_gemini(
        "Qual foi o consumo?",
    )

    # O caminho da primeira chamada não mudou: _build_model()
    # sem argumento.
    assert built == [()]
    assert attempt.model == "gemini-3.1-flash-lite"


@pytest.mark.anyio
async def test_failed_call_reports_the_requested_model(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        gemini,
        "Agent",
        FailingAgent,
    )

    monkeypatch.setattr(
        gemini,
        "_build_model",
        lambda model_name=None: object(),
    )

    output, attempt = await gemini.run_gemini(
        "teste",
        model_name="gemini-ultimo-recurso",
    )

    assert output is None
    assert attempt.success is False
    assert attempt.model == "gemini-ultimo-recurso"
    assert attempt.error_type == ProviderErrorType.UNKNOWN


@pytest.mark.anyio
async def test_missing_api_key_reports_the_requested_model(
    monkeypatch,
):
    monkeypatch.setattr(
        gemini,
        "settings",
        make_settings(api_key=None),
    )

    output, attempt = await gemini.run_gemini(
        "teste",
        model_name="gemini-ultimo-recurso",
    )

    assert output is None
    assert attempt.model == "gemini-ultimo-recurso"
    assert (
        attempt.error_type
        == ProviderErrorType.CONFIGURATION_ERROR
    )