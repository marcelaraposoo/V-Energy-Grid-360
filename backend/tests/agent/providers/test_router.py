from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.agent.providers import router
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    ProviderName,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_settings():
    return SimpleNamespace(
        gemini_model="gemini",
        gemini_last_resort_model=None,
        openrouter_models=(
            "gemma-4",
            "nemotron-ultra",
        )
    )


def make_attempt(
    *,
    provider: ProviderName,
    model: str,
    attempt: int,
    success: bool,
    error_type: ProviderErrorType | None = None,
) -> ProviderAttempt:
    return ProviderAttempt(
        provider=provider,
        model=model,
        attempt=attempt,
        started_at=datetime.now(
            timezone.utc
        ),
        success=success,
        latency_ms=10.0,
        error_type=error_type,
    )


@pytest.mark.anyio
async def test_gemini_success_does_not_call_openrouter(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    openrouter_calls = []

    async def fake_gemini(
        prompt,
        *,
        output_type=str,
        instructions=None,
        attempt=1,
    ):
        return (
            "resposta gemini",
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=attempt,
                success=True,
            ),
        )

    async def fake_openrouter(
        *args,
        **kwargs,
    ):
        openrouter_calls.append(
            "called"
        )

        raise AssertionError(
            "OpenRouter não deveria ser chamado."
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output == "resposta gemini"
    assert error is None

    assert len(attempts) == 1
    assert attempts[0].success is True

    assert openrouter_calls == []


@pytest.mark.anyio
async def test_gemini_rate_limit_falls_back_to_openrouter(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    async def fake_gemini(
        prompt,
        *,
        output_type=str,
        instructions=None,
        attempt=1,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=attempt,
                success=False,
                error_type=(
                    ProviderErrorType.RATE_LIMITED
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        output_type=str,
        instructions=None,
        attempt=1,
    ):
        return (
            "resposta openrouter",
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=True,
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert (
        output
        == "resposta openrouter"
    )

    assert error is None

    assert len(attempts) == 2

    assert (
        attempts[0].provider
        == ProviderName.GEMINI
    )

    assert (
        attempts[1].provider
        == ProviderName.OPENROUTER
    )

    # Primeiro fallback agora é Gemma.
    assert (
        attempts[1].model
        == "gemma-4"
    )


@pytest.mark.anyio
async def test_gemini_quota_exhausted_uses_openrouter(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.QUOTA_EXHAUSTED
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt=2,
        **kwargs,
    ):
        return (
            "fallback ok",
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=True,
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output == "fallback ok"
    assert error is None

    assert len(attempts) == 2

    assert (
        attempts[1].model
        == "gemma-4"
    )


@pytest.mark.anyio
async def test_nonrecoverable_gemini_error_stops_flow(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    openrouter_calls = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.UNAUTHORIZED
                ),
            ),
        )

    async def fake_openrouter(
        *args,
        **kwargs,
    ):
        openrouter_calls.append(
            "called"
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output is None

    assert (
        error
        == ProviderErrorType.UNAUTHORIZED
    )

    assert len(attempts) == 1

    assert openrouter_calls == []


@pytest.mark.anyio
async def test_openrouter_moves_to_next_model_after_rate_limit(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    called_models = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.TIMEOUT
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt,
        **kwargs,
    ):
        called_models.append(
            model_name
        )

        if model_name == "gemma-4":
            return (
                None,
                make_attempt(
                    provider=(
                        ProviderName.OPENROUTER
                    ),
                    model=model_name,
                    attempt=attempt,
                    success=False,
                    error_type=(
                        ProviderErrorType.RATE_LIMITED
                    ),
                ),
            )

        return (
            "ultra respondeu",
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=True,
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output == "ultra respondeu"
    assert error is None

    assert called_models == [
        "gemma-4",
        "nemotron-ultra",
    ]

    assert len(attempts) == 3

    assert attempts[0].attempt == 1
    assert attempts[1].attempt == 2
    assert attempts[2].attempt == 3


@pytest.mark.anyio
async def test_openrouter_quota_exhausted_stops_openrouter_loop(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    called_models = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.TIMEOUT
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt,
        **kwargs,
    ):
        called_models.append(
            model_name
        )

        return (
            None,
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=False,
                error_type=(
                    ProviderErrorType.QUOTA_EXHAUSTED
                ),
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output is None

    assert (
        error
        == ProviderErrorType.QUOTA_EXHAUSTED
    )

    # Se a conta inteira do OpenRouter
    # esgotou a cota, não adianta tentar
    # outro modelo do mesmo provider.
    assert called_models == [
        "gemma-4",
    ]

    assert len(attempts) == 2


@pytest.mark.anyio
async def test_openrouter_bad_request_stops_fallback(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    called_models = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.TIMEOUT
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt,
        **kwargs,
    ):
        called_models.append(
            model_name
        )

        return (
            None,
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=False,
                error_type=(
                    ProviderErrorType.BAD_REQUEST
                ),
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output is None

    assert (
        error
        == ProviderErrorType.BAD_REQUEST
    )

    # BAD_REQUEST indica problema da requisição,
    # não indisponibilidade específica do modelo.
    assert called_models == [
        "gemma-4",
    ]

    assert len(attempts) == 2


@pytest.mark.anyio
async def test_invalid_output_uses_next_model(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    called_models = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.INVALID_OUTPUT
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt,
        **kwargs,
    ):
        called_models.append(
            model_name
        )

        return (
            "resultado válido",
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=True,
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output == "resultado válido"
    assert error is None

    # Primeiro fallback deve ser Gemma.
    assert called_models == [
        "gemma-4",
    ]

    assert len(attempts) == 2


@pytest.mark.anyio
async def test_all_providers_fail_with_recoverable_errors(
    monkeypatch,
    fake_settings,
):
    monkeypatch.setattr(
        router,
        "settings",
        fake_settings,
    )

    called_models = []

    async def fake_gemini(
        prompt,
        **kwargs,
    ):
        return (
            None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model="gemini",
                attempt=1,
                success=False,
                error_type=(
                    ProviderErrorType.TIMEOUT
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        attempt,
        **kwargs,
    ):
        called_models.append(
            model_name
        )

        return (
            None,
            make_attempt(
                provider=(
                    ProviderName.OPENROUTER
                ),
                model=model_name,
                attempt=attempt,
                success=False,
                error_type=(
                    ProviderErrorType.PROVIDER_UNAVAILABLE
                ),
            ),
        )

    monkeypatch.setattr(
        router,
        "run_gemini",
        fake_gemini,
    )

    monkeypatch.setattr(
        router,
        "run_openrouter",
        fake_openrouter,
    )

    output, attempts, error = (
        await router.run_with_fallback(
            "teste"
        )
    )

    assert output is None

    assert (
        error
        == ProviderErrorType.PROVIDER_UNAVAILABLE
    )

    # Pool atual:
    # Gemini → Gemma → Nemotron Ultra
    assert called_models == [
        "gemma-4",
        "nemotron-ultra",
    ]

    assert len(attempts) == 3

    assert [
        attempt.attempt
        for attempt in attempts
    ] == [
        1,
        2,
        3,
    ]


LAST_RESORT = "gemini-ultimo-recurso"


def _settings(last_resort=LAST_RESORT, primary="gemini"):
    return SimpleNamespace(
        gemini_model=primary,
        gemini_last_resort_model=last_resort,
        openrouter_models=("cohere", "nemotron-ultra"),
    )


def _install_fakes(
    monkeypatch,
    *,
    openrouter_error=ProviderErrorType.RATE_LIMITED,
    openrouter_success=False,
    last_resort_success=False,
):
    gemini_calls = []
    openrouter_calls = []

    async def fake_gemini(
        prompt,
        *,
        output_type=str,
        instructions=None,
        attempt=1,
        model_name=None,
    ):
        gemini_calls.append(model_name)

        success = model_name is not None and last_resort_success

        return (
            "resposta último recurso" if success else None,
            make_attempt(
                provider=ProviderName.GEMINI,
                model=model_name or "gemini",
                attempt=attempt,
                success=success,
                error_type=(
                    None
                    if success
                    else ProviderErrorType.PROVIDER_UNAVAILABLE
                ),
            ),
        )

    async def fake_openrouter(
        model_name,
        prompt,
        *,
        output_type=str,
        instructions=None,
        attempt=1,
    ):
        openrouter_calls.append(model_name)

        return (
            "resposta openrouter" if openrouter_success else None,
            make_attempt(
                provider=ProviderName.OPENROUTER,
                model=model_name,
                attempt=attempt,
                success=openrouter_success,
                error_type=(
                    None if openrouter_success else openrouter_error
                ),
            ),
        )

    monkeypatch.setattr(router, "run_gemini", fake_gemini)
    monkeypatch.setattr(router, "run_openrouter", fake_openrouter)

    return gemini_calls, openrouter_calls


@pytest.mark.anyio
async def test_last_resort_answers_after_all_others_fail(monkeypatch):
    monkeypatch.setattr(router, "settings", _settings())
    gemini_calls, openrouter_calls = _install_fakes(
        monkeypatch, last_resort_success=True
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output == "resposta último recurso"
    assert error is None
    assert [a.model for a in attempts] == [
        "gemini", "cohere", "nemotron-ultra", LAST_RESORT,
    ]
    assert [a.attempt for a in attempts] == [1, 2, 3, 4]
    assert gemini_calls == [None, LAST_RESORT]
    assert openrouter_calls == ["cohere", "nemotron-ultra"]


@pytest.mark.anyio
async def test_all_providers_including_last_resort_fail(monkeypatch):
    monkeypatch.setattr(router, "settings", _settings())
    _install_fakes(monkeypatch, last_resort_success=False)

    output, attempts, error = await router.run_with_fallback("teste")

    assert output is None
    assert error == ProviderErrorType.PROVIDER_UNAVAILABLE
    assert len(attempts) == 4


@pytest.mark.anyio
async def test_openrouter_quota_exhausted_continues_to_last_resort(
    monkeypatch,
):
    monkeypatch.setattr(router, "settings", _settings())
    gemini_calls, openrouter_calls = _install_fakes(
        monkeypatch,
        openrouter_error=ProviderErrorType.QUOTA_EXHAUSTED,
        last_resort_success=True,
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output == "resposta último recurso"
    assert error is None
    # A cota esgotada encerra só o laço do OpenRouter.
    assert openrouter_calls == ["cohere"]
    assert gemini_calls == [None, LAST_RESORT]
    assert [a.attempt for a in attempts] == [1, 2, 3]


@pytest.mark.anyio
async def test_quota_exhausted_is_reported_when_last_resort_fails(
    monkeypatch,
):
    monkeypatch.setattr(router, "settings", _settings())
    _install_fakes(
        monkeypatch,
        openrouter_error=ProviderErrorType.QUOTA_EXHAUSTED,
        last_resort_success=False,
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output is None
    assert error == ProviderErrorType.QUOTA_EXHAUSTED
    assert len(attempts) == 3


@pytest.mark.anyio
async def test_last_resort_is_not_called_when_openrouter_answers(
    monkeypatch,
):
    monkeypatch.setattr(router, "settings", _settings())
    gemini_calls, _ = _install_fakes(
        monkeypatch, openrouter_success=True
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output == "resposta openrouter"
    assert error is None
    assert gemini_calls == [None]
    assert len(attempts) == 2


@pytest.mark.anyio
async def test_last_resort_is_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(router, "settings", _settings(last_resort=None))
    gemini_calls, _ = _install_fakes(monkeypatch)

    output, attempts, error = await router.run_with_fallback("teste")

    assert output is None
    assert error == ProviderErrorType.PROVIDER_UNAVAILABLE
    assert gemini_calls == [None]
    assert len(attempts) == 3


@pytest.mark.anyio
async def test_last_resort_is_skipped_when_equal_to_primary(monkeypatch):
    monkeypatch.setattr(
        router,
        "settings",
        _settings(last_resort="gemini", primary="gemini"),
    )
    gemini_calls, _ = _install_fakes(monkeypatch)

    await router.run_with_fallback("teste")

    assert gemini_calls == [None]


@pytest.mark.anyio
async def test_nonrecoverable_openrouter_error_skips_last_resort(
    monkeypatch,
):
    monkeypatch.setattr(router, "settings", _settings())
    gemini_calls, _ = _install_fakes(
        monkeypatch,
        openrouter_error=ProviderErrorType.BAD_REQUEST,
        last_resort_success=True,
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output is None
    assert error == ProviderErrorType.BAD_REQUEST
    assert gemini_calls == [None]


@pytest.mark.anyio
async def test_openrouter_configuration_error_continues_to_last_resort(
    monkeypatch,
):
    monkeypatch.setattr(router, "settings", _settings())
    gemini_calls, openrouter_calls = _install_fakes(
        monkeypatch,
        openrouter_error=ProviderErrorType.CONFIGURATION_ERROR,
        last_resort_success=True,
    )

    output, attempts, error = await router.run_with_fallback("teste")

    assert output == "resposta último recurso"
    assert error is None
    assert openrouter_calls == ["cohere"]
    assert gemini_calls == [None, LAST_RESORT]