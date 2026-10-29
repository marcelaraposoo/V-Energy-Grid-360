from app.agent.schemas import SQLExecutionErrorType


DEFAULT_EXECUTION_MESSAGE = (
    "Não foi possível consultar os dados para essa pergunta. "
    "Tente reformulá-la."
)

EXECUTION_MESSAGES = {
    SQLExecutionErrorType.TABLE_NOT_FOUND: DEFAULT_EXECUTION_MESSAGE,
    SQLExecutionErrorType.COLUMN_NOT_FOUND: DEFAULT_EXECUTION_MESSAGE,
    SQLExecutionErrorType.TIMEOUT: (
        "A consulta demorou mais do que o esperado. "
        "Tente uma pergunta mais específica, por exemplo com um "
        "período ou município."
    ),
    SQLExecutionErrorType.DATABASE_UNAVAILABLE: (
        "A base de dados está temporariamente indisponível. "
        "Tente novamente em alguns instantes."
    ),
    SQLExecutionErrorType.EXECUTION_ERROR: DEFAULT_EXECUTION_MESSAGE,
}


def get_execution_message(
    error: SQLExecutionErrorType | None,
) -> str:
    if error is None:
        return DEFAULT_EXECUTION_MESSAGE

    return EXECUTION_MESSAGES.get(error, DEFAULT_EXECUTION_MESSAGE)