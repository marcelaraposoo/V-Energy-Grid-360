import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.agent.guardrails.output_rules import extract_numbers
from app.agent.schemas import QueryExecutionResult


# Deve ser igual a MAX_ROWS_IN_PROMPT, de answer_synthesizer.py.
# Um teste garante que os dois valores não se separem.
MAX_ROWS_SHOWN = 50

_ISO_DATE_PATTERN = re.compile(
    r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])(?:-(\d{2}))?\b"
)


@dataclass(frozen=True)
class AllowedNumbers:
    values: tuple[Decimal, ...]
    derived_enabled: bool


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            return None

        number = Decimal(str(value))
    else:
        return None

    return number if number.is_finite() else None


def _numbers_in_text(text: str) -> list[Decimal]:
    values: list[Decimal] = []

    for number in extract_numbers(text):
        values.extend(number.candidates)

    return values


def _date_components(text: str) -> list[Decimal]:
    values: list[Decimal] = []

    for match in _ISO_DATE_PATTERN.finditer(text):
        for group in match.groups():
            if group:
                values.append(Decimal(int(group)))

    return values


def _derived_values(column: list[Decimal]) -> list[Decimal]:
    if not column:
        return []

    total = sum(column, Decimal(0))
    count = Decimal(len(column))

    derived = [
        total,
        total / count,
        min(column),
        max(column),
        count,
    ]

    if total != 0 and all(value >= 0 for value in column):
        derived.extend(
            value / total * 100 for value in column
        )

    return derived


def build_allowed_numbers(
    question: str,
    sql: str,
    result: QueryExecutionResult,
    *,
    max_rows_shown: int = MAX_ROWS_SHOWN,
) -> AllowedNumbers:
    """
    Monta o conjunto de números que a resposta pode citar.

    Entram como evidência: valores das linhas (e números dentro
    dos textos das células), row_count, linhas enviadas, posições
    e, só com resultado completo, soma, média, mínimo, máximo,
    contagem e participação no total de cada coluna.

    Entram como contexto: números e datas do SQL executado, que
    foi gerado a partir do filtro real (período, limite, limiar).

    NÃO entram: números da pergunta do usuário e constantes
    globais. Quem escreve a pergunta pode afirmar qualquer valor,
    e isso não é evidência do que o banco retornou. O parâmetro
    question continua na assinatura para não alterar os chamadores.
    """

    shown_rows = result.rows[:max_rows_shown]

    values: list[Decimal] = []

    values.extend(_numbers_in_text(sql))
    values.extend(_date_components(sql))

    values.append(Decimal(result.row_count))
    values.append(Decimal(len(shown_rows)))
    values.extend(
        Decimal(position)
        for position in range(1, len(shown_rows) + 1)
    )

    columns: dict[int, list[Decimal]] = {}

    for row in shown_rows:
        for index, cell in enumerate(row):
            number = _to_decimal(cell)

            if number is not None:
                values.append(number)
                columns.setdefault(index, []).append(number)
            elif isinstance(cell, str):
                values.extend(_numbers_in_text(cell))
                values.extend(_date_components(cell))

    derived_enabled = (
        not result.truncated
        and result.row_count == len(result.rows)
        and len(result.rows) <= max_rows_shown
    )

    if derived_enabled:
        for column in columns.values():
            values.extend(_derived_values(column))

    return AllowedNumbers(
        values=tuple(abs(value) for value in values),
        derived_enabled=derived_enabled,
    )


def _tolerance(candidate: Decimal) -> Decimal:
    exponent = candidate.as_tuple().exponent

    # Meia unidade da última casa escrita.
    return Decimal(5).scaleb(int(exponent) - 1)


def is_number_supported(
    candidates: tuple[Decimal, ...],
    allowed: AllowedNumbers,
) -> bool:
    """
    Um número do texto é suportado se qualquer uma das suas
    interpretações bate com um valor permitido, dentro da
    tolerância de arredondamento.

    Sem interpretações (formato inválido), não é suportado.
    """

    for candidate in candidates:
        tolerance = _tolerance(candidate)

        if any(
            abs(allowed_value - candidate) <= tolerance
            for allowed_value in allowed.values
        ):
            return True

    return False