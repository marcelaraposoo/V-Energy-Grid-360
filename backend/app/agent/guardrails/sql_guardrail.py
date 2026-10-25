from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.agent.schemas import (
    SQLGuardrailDecision,
    SQLGuardrailReason,
    SQLGuardrailResult,
)


SQL_DIALECT = "sqlite"


FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
)


UNSUPPORTED_EXPRESSIONS = (
    exp.Window,
)


RETRY_MESSAGES = {
    SQLGuardrailReason.INVALID_SQL: (
        "A consulta SQL anterior é inválida ou não pôde "
        "ser interpretada. Gere uma nova consulta SQL válida."
    ),
    SQLGuardrailReason.MULTIPLE_STATEMENTS: (
        "A consulta anterior contém mais de uma instrução SQL. "
        "Gere exatamente uma única consulta."
    ),
    SQLGuardrailReason.FORBIDDEN_OPERATION: (
        "A consulta anterior contém uma operação não permitida. "
        "Gere somente uma consulta de leitura."
    ),
    SQLGuardrailReason.UNSUPPORTED_QUERY: (
        "A consulta anterior utiliza uma estrutura SQL não "
        "suportada nesta etapa. Gere uma versão mais simples "
        "utilizando apenas as estruturas permitidas."
    ),
}


def _allow(sql: str) -> SQLGuardrailResult:
    return SQLGuardrailResult(
        decision=SQLGuardrailDecision.ALLOW,
        reason=None,
        retryable=False,
        original_sql=sql,
    )


def _block(
    sql: str,
    reason: SQLGuardrailReason,
    *,
    retryable: bool = True,
) -> SQLGuardrailResult:
    return SQLGuardrailResult(
        decision=SQLGuardrailDecision.BLOCK,
        reason=reason,
        retryable=retryable,
        original_sql=sql,
    )


def _contains_forbidden_operation(
    expression: exp.Expression,
) -> bool:
    return any(
        expression.find(expression_type) is not None
        for expression_type in FORBIDDEN_EXPRESSIONS
    )


def _contains_unsupported_expression(
    expression: exp.Expression,
) -> bool:
    return any(
        expression.find(expression_type) is not None
        for expression_type in UNSUPPORTED_EXPRESSIONS
    )


def _is_read_only_query(
    expression: exp.Expression,
) -> bool:
    return isinstance(
        expression,
        (
            exp.Select,
            exp.Union,
            exp.Intersect,
            exp.Except,
        ),
    )


def build_retry_feedback(
    result: SQLGuardrailResult,
) -> str | None:

    if (
        result.decision != SQLGuardrailDecision.BLOCK
        or not result.retryable
        or result.reason is None
    ):
        return None

    reason_message = RETRY_MESSAGES.get(
        result.reason
    )

    if reason_message is None:
        return None

    return (
        "A consulta SQL anterior foi rejeitada pelo "
        "SQL Guardrail.\n\n"
        "SQL anterior rejeitado:\n"
        f"{result.original_sql}\n\n"
        "Motivo da rejeição:\n"
        f"{reason_message}\n\n"
        "Gere uma nova consulta corrigida, mantendo "
        "a intenção original do usuário e respeitando "
        "todas as regras da etapa de geração SQL."
    )


def validate_sql(
    sql: str,
) -> SQLGuardrailResult:
    if not sql or not sql.strip():
        return _block(
            sql,
            SQLGuardrailReason.INVALID_SQL,
        )

    try:
        statements = parse(
            sql,
            dialect=SQL_DIALECT,
        )

        statements = [
            statement
            for statement in statements
            if statement is not None
        ]

        if not statements:
            return _block(
                sql,
                SQLGuardrailReason.INVALID_SQL,
            )

        if len(statements) != 1:
            return _block(
                sql,
                SQLGuardrailReason.MULTIPLE_STATEMENTS,
            )

        statement = statements[0]

        if _contains_forbidden_operation(
            statement
        ):
            return _block(
                sql,
                SQLGuardrailReason.FORBIDDEN_OPERATION,
            )

        if not _is_read_only_query(
            statement
        ):
            return _block(
                sql,
                SQLGuardrailReason.INVALID_SQL,
            )

        if _contains_unsupported_expression(
            statement
        ):
            return _block(
                sql,
                SQLGuardrailReason.UNSUPPORTED_QUERY,
            )

        return _allow(sql)

    except ParseError:
        return _block(
            sql,
            SQLGuardrailReason.INVALID_SQL,
        )

    except Exception:
        return _block(
            sql,
            SQLGuardrailReason.GUARDRAIL_INTERNAL_ERROR,
            retryable=False,
        )