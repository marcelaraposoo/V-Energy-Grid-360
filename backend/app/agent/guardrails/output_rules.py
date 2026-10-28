import re
from dataclasses import dataclass
from decimal import Decimal


# Datas (ISO e brasileiro). São extraídas como datas próprias, para
# serem validadas, e removidas do texto antes da extração de números,
# para não virarem números soltos. A extração e a remoção usam o mesmo
# código (_scan_dates), então nenhuma data some sem ser verificada.
_ISO_DATE_PATTERN = re.compile(
    r"\b((?:19|20)\d{2})-(0[1-9]|1[0-2])(?:-(\d{2}))?\b"
)
_FULL_DATE_PATTERN = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])/(0?[1-9]|1[0-2])/(\d{4}|\d{2})\b"
)
_MONTH_YEAR_PATTERN = re.compile(
    r"\b(0?[1-9]|1[0-2])/((?:19|20)\d{2})\b"
)

# Numeração de listas no início da linha ("1. ", "2) ").
_LIST_MARKER_PATTERN = re.compile(
    r"(?m)^[ \t]*\d{1,2}[.)][ \t]+"
)

# Dígitos com separadores '.' ou ',' entre grupos.
# O lookbehind ignora dígitos colados em letras ou outros
# dígitos (ex.: B1, A4).
_NUMBER_PATTERN = re.compile(r"(?<!\w)\d+(?:[.,]\d+)*")


@dataclass(frozen=True)
class ExtractedNumber:
    raw: str
    # Interpretações possíveis do valor. Vazio = formato
    # inválido, que a verificação trata como não suportado.
    candidates: tuple[Decimal, ...]


@dataclass(frozen=True)
class ExtractedDate:
    raw: str
    year: int
    month: int
    day: int | None

    @property
    def key(self) -> tuple[int, int, int | None]:
        return (self.year, self.month, self.day)


def _from_iso(match) -> ExtractedDate:
    year, month, day = match.groups()

    return ExtractedDate(
        raw=match.group(),
        year=int(year),
        month=int(month),
        day=int(day) if day else None,
    )


def _from_full_date(match) -> ExtractedDate:
    day, month, year = match.groups()

    # Ano de dois dígitos é lido como 20xx.
    full_year = int(year) + (2000 if len(year) == 2 else 0)

    return ExtractedDate(
        raw=match.group(),
        year=full_year,
        month=int(month),
        day=int(day),
    )


def _from_month_year(match) -> ExtractedDate:
    month, year = match.groups()

    return ExtractedDate(
        raw=match.group(),
        year=int(year),
        month=int(month),
        day=None,
    )


# A ordem importa: uma data completa é consumida antes que o
# "mês/ano" dentro dela possa ser lido de novo.
_DATE_RULES = (
    (_ISO_DATE_PATTERN, _from_iso),
    (_FULL_DATE_PATTERN, _from_full_date),
    (_MONTH_YEAR_PATTERN, _from_month_year),
)


def _scan_dates(text: str) -> tuple[list[ExtractedDate], str]:
    """
    Devolve as datas encontradas e o texto sem elas.
    """

    dates: list[ExtractedDate] = []
    cleaned = text

    for pattern, build in _DATE_RULES:
        for match in pattern.finditer(cleaned):
            dates.append(build(match))

        cleaned = pattern.sub(" ", cleaned)

    return dates, cleaned


def extract_dates(text: str) -> list[ExtractedDate]:
    return _scan_dates(text)[0]


def _valid_thousands_groups(groups: list[str]) -> bool:
    """
    Valida agrupamento de milhares: o primeiro grupo tem de
    1 a 3 dígitos (sem zero à esquerda) e os demais têm
    exatamente 3 dígitos.
    """

    if len(groups) < 2:
        return False

    first, rest = groups[0], groups[1:]

    if not 1 <= len(first) <= 3:
        return False

    if first.startswith("0"):
        return False

    return all(len(group) == 3 for group in rest)


def parse_number_token(
    token: str,
) -> tuple[Decimal, ...]:
    """
    Converte um token numérico em valores possíveis.

    O expoente do Decimal preserva as casas decimais escritas
    (12,5 -> expoente -1), o que permite definir depois a
    tolerância de arredondamento.
    """

    if (
        not token
        or not token[0].isdigit()
        or not token[-1].isdigit()
    ):
        return ()

    has_dot = "." in token
    has_comma = "," in token

    if not has_dot and not has_comma:
        return (Decimal(token),)

    if has_dot and has_comma:
        decimal_sep = (
            "." if token.rfind(".") > token.rfind(",") else ","
        )
        thousands_sep = "," if decimal_sep == "." else "."

        integer_part, fraction = token.rsplit(decimal_sep, 1)
        groups = integer_part.split(thousands_sep)

        if (
            decimal_sep in integer_part
            or not _valid_thousands_groups(groups)
        ):
            return ()

        return (Decimal("".join(groups) + "." + fraction),)

    separator = "." if has_dot else ","
    parts = token.split(separator)

    if len(parts) > 2:
        if _valid_thousands_groups(parts):
            return (Decimal("".join(parts)),)

        return ()

    before, after = parts

    # "4.820" pode ser 4820 (milhar) ou 4,82 (decimal).
    if len(after) == 3 and _valid_thousands_groups(parts):
        return (
            Decimal(before + after),
            Decimal(before + "." + after),
        )

    return (Decimal(before + "." + after),)


def _remove_non_numeric_noise(text: str) -> str:
    cleaned = _scan_dates(text)[1]

    return _LIST_MARKER_PATTERN.sub("", cleaned)


def extract_numbers(text: str) -> list[ExtractedNumber]:
    cleaned = _remove_non_numeric_noise(text)

    return [
        ExtractedNumber(
            raw=match.group(),
            candidates=parse_number_token(match.group()),
        )
        for match in _NUMBER_PATTERN.finditer(cleaned)
    ]