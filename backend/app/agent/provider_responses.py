from app.agent.schemas import ProviderErrorType


DEFAULT_PROVIDER_MESSAGE = (
    "Não foi possível processar sua solicitação neste momento. "
    "Tente novamente em alguns instantes."
)


PROVIDER_MESSAGES = {
    ProviderErrorType.RATE_LIMITED: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível. "
        "Tente novamente em alguns instantes."
    ),
    ProviderErrorType.QUOTA_EXHAUSTED: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível. "
        "Tente novamente mais tarde."
    ),
    ProviderErrorType.PROVIDER_UNAVAILABLE: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível. "
        "Tente novamente em alguns instantes."
    ),
    ProviderErrorType.TIMEOUT: (
        "A solicitação demorou mais do que o esperado. "
        "Tente novamente."
    ),
    ProviderErrorType.CONNECTION_ERROR: (
        "Não foi possível acessar o serviço de "
        "inteligência artificial neste momento. "
        "Tente novamente."
    ),
    ProviderErrorType.INVALID_OUTPUT: (
        "Não foi possível gerar uma resposta válida "
        "neste momento. Tente novamente."
    ),
    ProviderErrorType.BAD_REQUEST: (
        "Não foi possível processar sua solicitação "
        "neste momento."
    ),
    ProviderErrorType.UNAUTHORIZED: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível."
    ),
    ProviderErrorType.FORBIDDEN: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível."
    ),
    ProviderErrorType.CONFIGURATION_ERROR: (
        "O serviço de inteligência artificial está "
        "temporariamente indisponível."
    ),
    ProviderErrorType.UNKNOWN: (
        "Não foi possível processar sua solicitação "
        "neste momento. Tente novamente."
    ),
}


def get_provider_message(
    error: ProviderErrorType | None,
) -> str:
    if error is None:
        return DEFAULT_PROVIDER_MESSAGE

    return PROVIDER_MESSAGES.get(
        error,
        DEFAULT_PROVIDER_MESSAGE,
    )