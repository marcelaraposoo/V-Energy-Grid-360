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

    final_error = ProviderErrorType.PROVIDER_UNAVAILABLE

    for model_name in settings.openrouter_models:
        output, provider_attempt = (
            await run_openrouter(
                model_name,
                prompt,
                output_type=output_type,
                instructions=instructions,
                attempt=len(attempts) + 1,
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
            # A conta do OpenRouter esgotou: trocar de modelo
            # nele não resolve, mas o último recurso é outro
            # provedor.
            final_error = ProviderErrorType.QUOTA_EXHAUSTED
            break

        if (
            error_type
            not in RECOVERABLE_ERRORS
        ):
            return (
                None,
                attempts,
                error_type,
            )

    # =====================================================
    # 3. ÚLTIMO RECURSO (Gemini)
    # =====================================================

    last_resort = settings.gemini_last_resort_model

    if last_resort and last_resort != settings.gemini_model:
        output, last_attempt = await run_gemini(
            prompt,
            output_type=output_type,
            instructions=instructions,
            attempt=len(attempts) + 1,
            model_name=last_resort,
        )

        attempts.append(
            last_attempt
        )

        if last_attempt.success:
            return (
                output,
                attempts,
                None,
            )

    return (
        None,
        attempts,
        final_error,
    )