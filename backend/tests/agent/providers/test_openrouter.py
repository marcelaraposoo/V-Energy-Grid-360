from types import SimpleNamespace

import pytest
from pydantic_ai.exceptions import ModelAPIError

from app.agent.providers import openrouter
from app.agent.schemas import (
    ProviderErrorType,
    ProviderName,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_settings(
    api_key: str | None = "fake-key",
):
    return SimpleNamespace(
        openrouter_api_key=api_key,
        provider_timeout_seconds=20.0,
    )


class FakeResult:
    def __init__(
        self,
        output,
    ):
        self.output = output


class SuccessfulAgent:
    def __init__(
        self,
        *args,
        **kwargs,
    ):
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
    def __init__(
        self,
        *args,
        **kwargs,
    ):
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
        openrouter,
        "settings",
        make_settings(
            api_key=None
        ),
    )

    usage_calls = []

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: usage_calls.append(
            "usage"
        ),
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "teste",
        )
    )

    assert output is None

    assert (
        attempt.provider
        == ProviderName.OPENROUTER
    )

    assert (
        attempt.model
        == "modelo-teste"
    )

    assert attempt.attempt == 1
    assert attempt.success is False
    assert attempt.latency_ms == 0.0

    assert (
        attempt.error_type
        == (
            ProviderErrorType
            .CONFIGURATION_ERROR
        )
    )

    # Sem chave, nenhuma chamada real
    # deve ser registrada.
    assert usage_calls == []


@pytest.mark.anyio
async def test_successful_openrouter_call(
    monkeypatch,
):
    monkeypatch.setattr(
        openrouter,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        openrouter,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        openrouter,
        "_build_model",
        lambda model_name: object(),
    )

    usage_calls = []

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: usage_calls.append(
            "usage"
        ),
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "Qual foi o consumo?",
        )
    )

    assert output == "resposta simulada"

    assert (
        attempt.provider
        == ProviderName.OPENROUTER
    )

    assert (
        attempt.model
        == "modelo-teste"
    )

    assert attempt.attempt == 1
    assert attempt.success is True
    assert attempt.error_type is None

    assert attempt.latency_ms is not None
    assert attempt.latency_ms >= 0

    assert usage_calls == [
        "usage"
    ]


@pytest.mark.anyio
async def test_usage_is_registered_before_request(
    monkeypatch,
):
    monkeypatch.setattr(
        openrouter,
        "settings",
        make_settings(),
    )

    calls = []

    class OrderedAgent:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        async def run(
            self,
            *args,
            **kwargs,
        ):
            calls.append(
                "request"
            )

            return FakeResult(
                "ok"
            )

    monkeypatch.setattr(
        openrouter,
        "Agent",
        OrderedAgent,
    )

    monkeypatch.setattr(
        openrouter,
        "_build_model",
        lambda model_name: object(),
    )

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: calls.append(
            "usage"
        ),
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "teste",
        )
    )

    assert output == "ok"
    assert attempt.success is True

    assert calls == [
        "usage",
        "request",
    ]


@pytest.mark.anyio
async def test_failed_openrouter_call_is_still_registered(
    monkeypatch,
):
    monkeypatch.setattr(
        openrouter,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        openrouter,
        "Agent",
        FailingAgent,
    )

    monkeypatch.setattr(
        openrouter,
        "_build_model",
        lambda model_name: object(),
    )

    usage_calls = []

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: usage_calls.append(
            "usage"
        ),
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "teste",
        )
    )

    assert output is None

    assert (
        attempt.provider
        == ProviderName.OPENROUTER
    )

    assert attempt.success is False

    assert (
        attempt.error_type
        == ProviderErrorType.UNKNOWN
    )

    assert attempt.latency_ms is not None
    assert attempt.latency_ms >= 0

    # Mesmo falhando, a tentativa chegou
    # ao provider e deve ser contabilizada.
    assert usage_calls == [
        "usage"
    ]


@pytest.mark.anyio
async def test_attempt_number_is_preserved(
    monkeypatch,
):
    monkeypatch.setattr(
        openrouter,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        openrouter,
        "Agent",
        SuccessfulAgent,
    )

    monkeypatch.setattr(
        openrouter,
        "_build_model",
        lambda model_name: object(),
    )

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: None,
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "teste",
            attempt=3,
        )
    )

    assert output == "resposta simulada"
    assert attempt.attempt == 3
    assert attempt.success is True


@pytest.mark.anyio
async def test_instructions_are_passed_to_agent(
    monkeypatch,
):
    captured = {}

    class CapturingAgent:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            pass

        async def run(
            self,
            prompt,
            *,
            instructions=None,
            output_type=str,
        ):
            captured[
                "prompt"
            ] = prompt

            captured[
                "instructions"
            ] = instructions

            return FakeResult(
                "ok"
            )

    monkeypatch.setattr(
        openrouter,
        "settings",
        make_settings(),
    )

    monkeypatch.setattr(
        openrouter,
        "Agent",
        CapturingAgent,
    )

    monkeypatch.setattr(
        openrouter,
        "_build_model",
        lambda model_name: object(),
    )

    monkeypatch.setattr(
        openrouter,
        "register_request_attempt",
        lambda: None,
    )

    output, attempt = (
        await openrouter.run_openrouter(
            "modelo-teste",
            "Pergunta do usuário",
            instructions=(
                "Responda apenas com dados."
            ),
        )
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


def test_classify_unknown_error():
    error = RuntimeError(
        "erro qualquer"
    )

    result = (
        openrouter
        .classify_openrouter_error(
            error
        )
    )

    assert (
        result
        == ProviderErrorType.UNKNOWN
    )


def test_generic_model_api_error_is_recoverable():
    error = ModelAPIError(
        model_name="openrouter-test",
        message=(
            "Falha genérica simulada "
            "do provider."
        ),
    )

    result = (
        openrouter
        .classify_openrouter_error(
            error
        )
    )

    assert (
        result
        == (
            ProviderErrorType
            .PROVIDER_UNAVAILABLE
        )
    )