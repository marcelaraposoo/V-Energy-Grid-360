import asyncio
import logging
from datetime import datetime, timezone
from time import monotonic, perf_counter
from typing import Any

from app.agent.providers.data_policy import allows_model
from app.agent.providers.gemini import run_gemini
from app.agent.providers.openrouter import run_openrouter
from app.agent.providers.latency_policy import attempt_timeout, phase_deadline, request_policy
from app.agent.schemas import (
    ProviderAttempt, ProviderErrorType, ProviderName, SQLGenerationResult, SynthesisResult,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

RECOVERABLE_ERRORS = {
    ProviderErrorType.RATE_LIMITED,
    ProviderErrorType.PROVIDER_UNAVAILABLE,
    ProviderErrorType.TIMEOUT,
    ProviderErrorType.CONNECTION_ERROR,
    ProviderErrorType.INVALID_OUTPUT,
}
CREDENTIAL_ERRORS = {
    ProviderErrorType.UNAUTHORIZED,
    ProviderErrorType.FORBIDDEN,
    ProviderErrorType.CONFIGURATION_ERROR,
}
PROVIDER_WIDE_ERRORS = {*CREDENTIAL_ERRORS, ProviderErrorType.QUOTA_EXHAUSTED}


def aggregate_errors(attempts: list[ProviderAttempt]) -> ProviderErrorType:
    """Falha terminal > quota > última falha, considerando a cadeia inteira.

    BAD_REQUEST/UNKNOWN interrompem a cadeia; quota conhecida mantém prioridade
    sobre falhas de disponibilidade/credenciais. Sucesso é tratado pelo chamador.
    """
    errors = [a.error_type or ProviderErrorType.UNKNOWN for a in attempts if not a.success]
    for error in reversed(errors):
        if error in {ProviderErrorType.BAD_REQUEST, ProviderErrorType.UNKNOWN}:
            return error
    if ProviderErrorType.QUOTA_EXHAUSTED in errors:
        return ProviderErrorType.QUOTA_EXHAUSTED
    return errors[-1] if errors else ProviderErrorType.PROVIDER_UNAVAILABLE


def supports_preference(provider, model, output_type):
    # Os adapters atuais suportam texto e os dois schemas via Native/PromptedOutput.
    # Um novo contrato exige avaliação explícita antes de reutilizar a preferência.
    return provider in {ProviderName.GEMINI, ProviderName.OPENROUTER} and output_type in (
        str, SQLGenerationResult, SynthesisResult,
    )


async def run_with_fallback(
    prompt: str,
    *,
    output_type: Any = str,
    instructions: str | None = None,
) -> tuple[Any | None, list[ProviderAttempt], ProviderErrorType | None]:
    attempts: list[ProviderAttempt] = []
    chain = [(ProviderName.GEMINI, settings.gemini_model)]
    for model in dict.fromkeys(settings.openrouter_models):
        if allows_model(model, getattr(settings, "provider_payload_policy", "confidential")):
            chain.append((ProviderName.OPENROUTER, model))
        else:
            logger.info("Modelo desabilitado pela política de dados provider=openrouter model=%s", model)
    last = settings.gemini_last_resort_model
    if last and last != settings.gemini_model:
        chain.append((ProviderName.GEMINI, last))

    policy = request_policy.get()
    preferred = policy.preferred if policy and getattr(settings, "provider_reuse_success", True) else None
    if preferred in chain and supports_preference(*preferred, output_type):
        chain.remove(preferred)
        chain.insert(0, preferred)

    disabled = set()
    for provider, model in chain:
        if provider in disabled:
            continue
        deadline = phase_deadline.get()
        remaining = deadline - monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            return None, attempts, ProviderErrorType.TIMEOUT
        timeout = settings.provider_timeout_seconds
        # O prazo curto é exclusivo do principal na primeira posição efetiva.
        if not attempts and (provider, model) == (ProviderName.GEMINI, settings.gemini_model):
            timeout = getattr(settings, "provider_primary_timeout_seconds", timeout)
        if remaining is not None:
            timeout = min(timeout, remaining)
        token = attempt_timeout.set(timeout)
        started_at = datetime.now(timezone.utc)
        start = perf_counter()
        try:
            # Engloba também o overhead local; aguarda cancelamento antes do fallback.
            async with asyncio.timeout(timeout):
                if provider == ProviderName.GEMINI:
                    kwargs = {} if model == settings.gemini_model else {"model_name": model}
                    output, current = await run_gemini(
                        prompt, output_type=output_type, instructions=instructions,
                        attempt=len(attempts) + 1, **kwargs,
                    )
                else:
                    output, current = await run_openrouter(
                        model, prompt, output_type=output_type, instructions=instructions,
                        attempt=len(attempts) + 1,
                    )
        except TimeoutError:
            output = None
            current = ProviderAttempt(
                provider=provider, model=model, attempt=len(attempts) + 1,
                started_at=started_at, success=False, error_type=ProviderErrorType.TIMEOUT,
                latency_ms=(perf_counter() - start) * 1000,
            )
        finally:
            attempt_timeout.reset(token)
        attempts.append(current)
        if current.success:
            if policy is not None:
                policy.preferred = (provider, model)
            return output, attempts, None
        if current.error_type in CREDENTIAL_ERRORS or (
            provider == ProviderName.OPENROUTER and current.error_type == ProviderErrorType.QUOTA_EXHAUSTED
        ):
            disabled.add(provider)
        elif current.error_type not in RECOVERABLE_ERRORS | PROVIDER_WIDE_ERRORS:
            return None, attempts, aggregate_errors(attempts)
    return None, attempts, aggregate_errors(attempts)
