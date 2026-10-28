import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.agent.guardrails.output_rules import (
    ExtractedDate,
    extract_dates,
    extract_numbers,
)
from app.agent.schemas import QueryExecutionResult


# Deve ser igual a MAX_ROWS_IN_PROMPT, de answer_synthesizer.py.
# Um teste garante que os dois valores não se separem.
MAX_ROWS_SHOWN = 50

# Períodos do diagnóstico, definidos no contrato Gold v1.
DIAGNOSTIC_PERIODS = {
    "PRIMEIRO_ANO": ((2022, 7), (2023, 6)),
    "ULTIMOS_12M": ((2025, 7), (2026, 6)),
}

_DIAGNOSTIC_PERIOD_PATTERN = re.compile(
    r"\b(PRIMEIRO_ANO|ULTIMOS_12M)\b",
    flags=re.IGNORECASE,
)

# (ano, mês, dia). O dia é None quando só o mês é conhecido.
DateKey = tuple[int, int, int | None]


@dataclass(frozen=True)
class AllowedNumbers:
    values: tuple[Decimal, ...]
    derived_enabled: bool
    dates: tuple[DateKey, ...] = ()


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


def _date_evidence(
    text: str,
) -> tuple[list[Decimal], list[DateKey]]:
    """
    Datas presentes em um texto (SQL ou célula do resultado), mais
    os limites dos períodos do diagnóstico quando o texto os nomeia.

    Devolve os componentes numéricos (ano, mês, dia), usados para
    validar números soltos como "2026", e as datas normalizadas.
    """

    components: list[Decimal] = []
    dates: list[DateKey] = []

    for date in extract_dates(text):
        dates.append(date.key)
        components.extend(
            Decimal(part) for part in date.key if part is not None
        )

    for match in _DIAGNOSTIC_PERIOD_PATTERN.finditer(text):
        for year, month in DIAGNOSTIC_PERIODS[match.group(1).upper()]:
            dates.append((year, month, None))
            components.extend((Decimal(year), Decimal(month)))

    return components, dates


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
    Monta o conjunto de números e datas que a resposta pode citar.

    Entram como evidência: valores das linhas (e números e datas
    dentro dos textos das células), row_count, linhas enviadas,
    posições e, só com resultado completo, soma, média, mínimo,
    máximo, contagem e participação no total de cada coluna.

    Entram como contexto: números e datas do SQL executado, que
    foi gerado a partir do filtro real (período, limite, limiar).

    NÃO entram: números e datas da pergunta do usuário e
    constantes globais. Quem escreve a pergunta pode afirmar
    qualquer valor, e isso não é evidência do que o banco
    retornou. O parâmetro question continua na assinatura para
    não alterar os chamadores.
    """

    shown_rows = result.rows[:max_rows_shown]

    values: list[Decimal] = []
    dates: list[DateKey] = []

    values.extend(_numbers_in_text(sql))

    sql_components, sql_dates = _date_evidence(sql)
    values.extend(sql_components)
    dates.extend(sql_dates)

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

                cell_components, cell_dates = _date_evidence(cell)
                values.extend(cell_components)
                dates.extend(cell_dates)

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
        dates=tuple(dict.fromkeys(dates)),
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


def is_date_supported(
    date: ExtractedDate,
    allowed: AllowedNumbers,
) -> bool:
    """
    Um mês é suportado se houver qualquer data permitida naquele
    mês. Um dia só é suportado se aquele dia exato for permitido.
    """

    for year, month, day in allowed.dates:
        if (year, month) != (date.year, date.month):
            continue

        if date.day is None or day == date.day:
            return True

    return False