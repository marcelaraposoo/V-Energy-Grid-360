import logging
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agent.schemas import (
    QueryExecutionResult,
    SQLExecutionErrorType,
    SQLExecutionOutcome,
    SQLExecutionStatus,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# Valores padrão. Os valores efetivos podem ser sobrescritos
# por parâmetro (usado nos testes).
DEFAULT_MAX_ROWS = 500
DEFAULT_TIMEOUT_SECONDS = 10.0

# O SQLite chama o handler a cada N instruções da máquina virtual.
_PROGRESS_INTERVAL = 50_000

_NO_SUCH_TABLE = re.compile(r"no such table", re.IGNORECASE)
_NO_SUCH_COLUMN = re.compile(r"no such column", re.IGNORECASE)

# Operações que uma consulta de leitura pode precisar. Tudo o mais
# (ATTACH, PRAGMA, escrita, DDL, funções de extensão) é negado.
_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


def _read_only_authorizer(
    action: int,
    arg1: str | None,
    arg2: str | None,
    db_name: str | None,
    trigger: str | None,
) -> int:
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK

    return sqlite3.SQLITE_DENY


def build_read_only_uri(path: str) -> str:
    """
    Abre o arquivo somente para leitura (mode=ro).

    as_uri() codifica espaços e barras do Windows, o que importa
    porque o projeto pode estar em pastas como 'Rocket Lab'.
    """

    return f"{Path(path).resolve().as_uri()}?mode=ro"


def _connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(
        build_read_only_uri(path),
        uri=True,
    )

    # Segunda barreira: mesmo que o arquivo permitisse escrita,
    # a conexão recusa qualquer instrução que altere dados.
    connection.execute("PRAGMA query_only = ON")

    # Terceira barreira: só leitura é autorizada. Bloqueia ATTACH,
    # PRAGMA e qualquer outra operação que não seja consulta.
    connection.set_authorizer(_read_only_authorizer)

    return connection


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<binário>"

    return str(value)


def classify_error(error: Exception) -> SQLExecutionErrorType:
    message = str(error)

    if isinstance(error, sqlite3.OperationalError):
        if "interrupted" in message.lower():
            return SQLExecutionErrorType.TIMEOUT

        if _NO_SUCH_TABLE.search(message):
            return SQLExecutionErrorType.TABLE_NOT_FOUND

        if _NO_SUCH_COLUMN.search(message):
            return SQLExecutionErrorType.COLUMN_NOT_FOUND

        if "unable to open" in message.lower():
            return SQLExecutionErrorType.DATABASE_UNAVAILABLE

    return SQLExecutionErrorType.EXECUTION_ERROR


def _failure(
    error_type: SQLExecutionErrorType,
    detail: str,
    started: float,
) -> SQLExecutionOutcome:
    return SQLExecutionOutcome(
        status=SQLExecutionStatus.FAILED,
        error_type=error_type,
        error_detail=detail[:300],
        elapsed_ms=(perf_counter() - started) * 1000,
    )


def execute_sql(
    sql: str,
    *,
    database_path: str | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SQLExecutionOutcome:
    """
    Executa um SQL já aprovado pela 4.2 e devolve um
    QueryExecutionResult dentro de um SQLExecutionOutcome.

    Barreiras: conexão somente leitura, timeout e limite de linhas.
    Esta função NÃO valida a estrutura do SQL (isso é da 4.2).
    """

    started = perf_counter()
    path = database_path or settings.sqlite_path

    try:
        connection = _connect(path)
    except Exception as error:
        logger.warning(
            "Banco indisponível. error_type=%s",
            type(error).__name__,
        )

        return _failure(
            SQLExecutionErrorType.DATABASE_UNAVAILABLE,
            f"{type(error).__name__}: {error}",
            started,
        )

    try:
        deadline = perf_counter() + timeout_seconds

        connection.set_progress_handler(
            lambda: 1 if perf_counter() > deadline else 0,
            _PROGRESS_INTERVAL,
        )

        cursor = connection.execute(sql)

        columns = [
            description[0]
            for description in (cursor.description or [])
        ]

        # Lê uma linha a mais que o limite, para saber se houve corte
        # sem precisar contar o total.
        fetched = cursor.fetchmany(max_rows + 1)

    except Exception as error:
        error_type = classify_error(error)

        # Só o tipo do erro vai ao log: a mensagem do SQLite pode
        # citar trechos do SQL, e valores de linhas não são logados.
        logger.warning(
            "Falha ao executar SQL. error_type=%s category=%s",
            type(error).__name__,
            error_type.value,
        )

        return _failure(
            error_type,
            f"{type(error).__name__}: {error}",
            started,
        )

    finally:
        connection.close()

    truncated = len(fetched) > max_rows
    rows_raw = fetched[:max_rows]

    rows = [
        [_normalize_value(value) for value in row]
        for row in rows_raw
    ]

    result = QueryExecutionResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
    )

    return SQLExecutionOutcome(
        status=SQLExecutionStatus.SUCCESS,
        result=result,
        elapsed_ms=(perf_counter() - started) * 1000,
    )