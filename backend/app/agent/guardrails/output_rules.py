import re
from dataclasses import dataclass
from decimal import Decimal


# Datas são removidas antes da extração: vêm da pergunta
# e do SQL, não são valores do resultado.
_DATE_PATTERNS = (
    re.compile(
        r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?:-\d{2})?\b"
    ),
    re.compile(
        r"\b(?:0?[1-9]|[12]\d|3[01])/"
        r"(?:0?[1-9]|1[0-2])/(?:\d{4}|\d{2})\b"
    ),
    re.compile(
        r"\b(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}\b"
    ),
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
    for pattern in _DATE_PATTERNS:
        text = pattern.sub(" ", text)

    return _LIST_MARKER_PATTERN.sub("", text)


def extract_numbers(text: str) -> list[ExtractedNumber]:
    cleaned = _remove_non_numeric_noise(text)

    return [
        ExtractedNumber(
            raw=match.group(),
            candidates=parse_number_token(match.group()),
        )
        for match in _NUMBER_PATTERN.finditer(cleaned)
    ]