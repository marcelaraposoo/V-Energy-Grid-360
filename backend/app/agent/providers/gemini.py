import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelHTTPError,
    ModelQuotaExceededError,
    ModelRateLimitError,
    ModelRequestTimeout,
    ModelServerError,
    ModelTimeoutError,
    ModelUnavailableError,
    UnexpectedModelBehavior,
)
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
    ProviderName,
)
from app.core.config import settings


logger = logging.getLogger(__name__)


def _build_model(
    model_name: str | None = None,
) -> GoogleModel:
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY não configurada."
        )

    provider = GoogleProvider(
        api_key=settings.gemini_api_key,
    )

    return GoogleModel(
        model_name or settings.gemini_model,
        provider=provider,
    )


def classify_gemini_error(
    error: Exception,
) -> ProviderErrorType:
    if isinstance(error, ModelQuotaExceededError):
        return ProviderErrorType.QUOTA_EXHAUSTED

    if isinstance(error, ModelRateLimitError):
        return ProviderErrorType.RATE_LIMITED

    if isinstance(
        error,
        (ModelTimeoutError, ModelRequestTimeout),
    ):
        return ProviderErrorType.TIMEOUT

    # Precisa vir depois do timeout,
    # pois ModelTimeoutError é ModelConnectionError.
    if isinstance(error, ModelConnectionError):
        return ProviderErrorType.CONNECTION_ERROR

    if isinstance(
        error,
        (ModelUnavailableError, ModelServerError),
    ):
        return ProviderErrorType.PROVIDER_UNAVAILABLE

    if isinstance(error, UnexpectedModelBehavior):
        return ProviderErrorType.INVALID_OUTPUT

    if isinstance(error, ModelHTTPError):
        status_errors = {
            400: ProviderErrorType.BAD_REQUEST,
            401: ProviderErrorType.UNAUTHORIZED,
            403: ProviderErrorType.FORBIDDEN,
        }

        if error.status_code in status_errors:
            return status_errors[error.status_code]

        if error.status_code >= 500:
            return ProviderErrorType.PROVIDER_UNAVAILABLE

    # ModelAPIError é a classe-base para falhas de API do provider.
    # Se o PydanticAI não conseguiu classificar a falha em uma
    # categoria mais específica, ainda permitimos o fallback para
    # o próximo provider/modelo.
    if isinstance(error, ModelAPIError):
        return ProviderErrorType.PROVIDER_UNAVAILABLE

    return ProviderErrorType.UNKNOWN


async def run_gemini(
    prompt: str,
    *,
    output_type: Any = str,
    instructions: str | None = None,
    attempt: int = 1,
    model_name: str | None = None,
) -> tuple[Any | None, ProviderAttempt]:
    resolved_model = model_name or settings.gemini_model
    started_at = datetime.now(timezone.utc)
    start = perf_counter()

    if not settings.gemini_api_key:
        provider_attempt = ProviderAttempt(
            provider=ProviderName.GEMINI,
            model=resolved_model,
            attempt=attempt,
            started_at=started_at,
            success=False,
            latency_ms=0.0,
            error_type=ProviderErrorType.CONFIGURATION_ERROR,
        )

        return None, provider_attempt

    try:
        model = (
            _build_model()
            if model_name is None
            else _build_model(model_name)
        )

        agent = Agent(
            model=model,
            retries={
                "tools": 0,
                "output": 0,
            },
            model_settings={
                "max_retries": 0,
                "request_timeout": (
                    settings.provider_timeout_seconds
                ),
            },
        )

        resolved_output_type = (
            str
            if output_type is str
            else NativeOutput(output_type)
        )

        result = await agent.run(
            prompt,
            instructions=instructions,
            output_type=resolved_output_type,
        )

        latency_ms = (
            perf_counter() - start
        ) * 1000

        provider_attempt = ProviderAttempt(
            provider=ProviderName.GEMINI,
            model=resolved_model,
            attempt=attempt,
            started_at=started_at,
            success=True,
            latency_ms=latency_ms,
            error_type=None,
        )

        return result.output, provider_attempt

    except Exception as error:
        latency_ms = (
            perf_counter() - start
        ) * 1000

        error_type = classify_gemini_error(
            error
        )

        if error_type == ProviderErrorType.UNKNOWN:
            logger.exception(
                "Erro Gemini não classificado. "
                "exception_type=%s cause_type=%s",
                type(error).__name__,
                (
                    type(error.__cause__).__name__
                    if error.__cause__
                    else None
                ),
            )

        provider_attempt = ProviderAttempt(
            provider=ProviderName.GEMINI,
            model=resolved_model,
            attempt=attempt,
            started_at=started_at,
            success=False,
            latency_ms=latency_ms,
            error_type=error_type,
        )

        return None, provider_attempt