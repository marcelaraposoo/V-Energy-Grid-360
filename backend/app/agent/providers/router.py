import logging
from typing import Any

from app.agent.providers.data_policy import allows_model
from app.agent.providers.gemini import run_gemini
from app.agent.providers.openrouter import run_openrouter
from app.agent.schemas import ProviderAttempt, ProviderErrorType
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


async def run_with_fallback(
    prompt: str,
    *,
    output_type: Any = str,
    instructions: str | None = None,
) -> tuple[Any | None, list[ProviderAttempt], ProviderErrorType | None]:
    attempts: list[ProviderAttempt] = []
    output, primary = await run_gemini(
        prompt, output_type=output_type, instructions=instructions, attempt=1,
    )
    attempts.append(primary)
    if primary.success:
        return output, attempts, None
    if primary.error_type not in RECOVERABLE_ERRORS | PROVIDER_WIDE_ERRORS:
        return None, attempts, aggregate_errors(attempts)

    # Uma credencial/configuração inválida vale para todos os modelos Gemini.
    gemini_credentials_invalid = primary.error_type in CREDENTIAL_ERRORS
    for model_name in dict.fromkeys(settings.openrouter_models):
        if not allows_model(model_name, getattr(settings, "provider_payload_policy", "confidential")):
            logger.info("Modelo desabilitado pela política de dados provider=openrouter model=%s", model_name)
            continue
        output, current = await run_openrouter(
            model_name, prompt, output_type=output_type, instructions=instructions,
            attempt=len(attempts) + 1,
        )
        attempts.append(current)
        if current.success:
            return output, attempts, None
        if current.error_type in PROVIDER_WIDE_ERRORS:
            # Encerra somente o pool OpenRouter, cuja credencial é independente.
            break
        if current.error_type not in RECOVERABLE_ERRORS:
            return None, attempts, aggregate_errors(attempts)

    last_resort = settings.gemini_last_resort_model
    if last_resort and last_resort != settings.gemini_model and not gemini_credentials_invalid:
        output, last = await run_gemini(
            prompt, output_type=output_type, instructions=instructions,
            attempt=len(attempts) + 1, model_name=last_resort,
        )
        attempts.append(last)
        if last.success:
            return output, attempts, None
    return None, attempts, aggregate_errors(attempts)
