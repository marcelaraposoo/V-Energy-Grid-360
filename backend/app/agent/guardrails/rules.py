import re
import unicodedata


MAX_INPUT_LENGTH = 500


SQL_PATTERNS = (
    r"\bSELECT\b[\s\S]*\bFROM\b",
    r"\bINSERT\s+INTO\b",
    r"\bUPDATE\b[\s\S]*\bSET\b",
    r"\bDELETE\s+FROM\b",
    r"\bDROP\s+(TABLE|DATABASE|VIEW)\b",
    r"\bALTER\s+TABLE\b",
    r"\bCREATE\s+(TABLE|DATABASE|VIEW)\b",
    r"\bTRUNCATE\s+TABLE\b",
)


URL_PATTERN = re.compile(
    r"\b(?:https?://|www\.)\S+",
    flags=re.IGNORECASE,
)


PROMPT_INJECTION_PATTERNS = (
    r"\bignore (todas )?(as )?(instruções|regras) (anteriores|prévias)\b",
    r"\bdesconsidere (todas )?(as )?(instruções|regras) (anteriores|prévias)\b",
    r"\bignore (suas|as) (instruções|regras)\b",
    r"\b(revele|mostre|exiba) (seu|o) (system prompt|prompt de sistema)\b",
    r"\ba partir de agora (você|voce) (é|e|será|sera)\b",

    r"\bignore (all )?(previous|prior) (instructions|rules)\b",
    r"\bdisregard (all )?(previous|prior) (instructions|rules)\b",
    r"\b(show|reveal) (your|the) system prompt\b",
)


def normalize_input(message: str) -> str:
    message = "".join(
        char
        for char in message
        if not unicodedata.category(char).startswith("C")
        or char in ("\n", "\t")
    )

    message = re.sub(r"\s+", " ", message)

    return message.strip()


def lacks_useful_content(message: str) -> bool:
    return not any(char.isalnum() for char in message)


def exceeds_max_length(message: str) -> bool:
    return len(message) > MAX_INPUT_LENGTH


def contains_direct_sql(message: str) -> bool:
    return any(
        re.search(pattern, message, flags=re.IGNORECASE)
        for pattern in SQL_PATTERNS
    )


def contains_url(message: str) -> bool:
    return bool(URL_PATTERN.search(message))


def matches_prompt_injection_pattern(message: str) -> bool:
    return any(
        re.search(pattern, message, flags=re.IGNORECASE)
        for pattern in PROMPT_INJECTION_PATTERNS
    )