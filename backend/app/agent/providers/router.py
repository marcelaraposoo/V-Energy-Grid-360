from typing import Any

from app.agent.providers.gemini import run_gemini
from app.agent.providers.openrouter import run_openrouter
from app.agent.schemas import (
    ProviderAttempt,
    ProviderErrorType,
)
from app.core.config import settings


RECOVERABLE_ERRORS = {
    ProviderErrorType.RATE_LIMITED,
    ProviderErrorType.PROVIDER_UNAVAILABLE,
    ProviderErrorType.TIMEOUT,
    ProviderErrorType.CONNECTION_ERROR,
    ProviderErrorType.INVALID_OUTPUT,
}

GEMINI_FALLBACK_ERRORS = {
    *RECOVERABLE_ERRORS,
    ProviderErrorType.QUOTA_EXHAUSTED,
    ProviderErrorType.CONFIGURATION_ERROR,
}

async def run_with_fallback(
    prompt: str,
    *,
    output_type: Any = str,
    instructions: str | None = None,
) -> tuple[
    Any | None,
    list[ProviderAttempt],
    ProviderErrorType | None,
]:
    attempts: list[ProviderAttempt] = []

    # =====================================================
    # 1. GEMINI
    # =====================================================

    output, gemini_attempt = await run_gemini(
        prompt,
        output_type=output_type,
        instructions=instructions,
        attempt=1,
    )

    attempts.append(
        gemini_attempt
    )

    if gemini_attempt.success:
        return (
            output,
            attempts,
            None,
        )

    if (
        gemini_attempt.error_type
        not in GEMINI_FALLBACK_ERRORS
    ):
        return (
            None,
            attempts,
            gemini_attempt.error_type,
        )

    # =====================================================
    # 2. OPENROUTER
    # =====================================================

    for attempt_number, model_name in enumerate(
        settings.openrouter_models,
        start=2,
    ):
        output, provider_attempt = (
            await run_openrouter(
                model_name,
                prompt,
                output_type=output_type,
                instructions=instructions,
                attempt=attempt_number,
            )
        )

        attempts.append(
            provider_attempt
        )

        if provider_attempt.success:
            return (
                output,
                attempts,
                None,
            )

        error_type = (
            provider_attempt.error_type
        )

        if (
            error_type
            == ProviderErrorType.QUOTA_EXHAUSTED
        ):
            return (
                None,
                attempts,
                ProviderErrorType.QUOTA_EXHAUSTED,
            )

        if (
            error_type
            not in RECOVERABLE_ERRORS
        ):
            return (
                None,
                attempts,
                error_type,
            )

    return (
        None,
        attempts,
        ProviderErrorType.PROVIDER_UNAVAILABLE,
    )