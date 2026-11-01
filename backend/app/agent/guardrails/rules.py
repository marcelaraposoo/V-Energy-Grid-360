import re
import unicodedata


MAX_INPUT_LENGTH = 500


# Projeções compactas: coluna, *, função simples e alias explícito.
# Reconhece assinaturas comuns sem interpretar toda a gramática SQL.
_SQL_PROJECTION = r"(?:\*|[\w.]+(?:\s*\([^()]*\))?)(?:\s+AS\s+\w+)?"

SQL_PATTERNS = (
    rf"\bSELECT\s+(?:DISTINCT\s+)?{_SQL_PROJECTION}"
    rf"(?:\s*,\s*{_SQL_PROJECTION})*\s+FROM\b",
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
    r"\b(ignore|desconsidere) (todas )?(as )?(instrucoes|regras) (anteriores|previas)\b",
    r"\b(ignore|desconsidere) (todas )?(as )?suas (instrucoes|regras)\b",
    r"\b(ignore|desconsidere) (todas )?(as )?(instrucoes|regras) (do agente|do sistema|de sistema)\b",
    # Comando genérico completo; qualificadores de negócio não entram aqui.
    r"\b(ignore|desconsidere) (todas )?(as )?(instrucoes|regras)[.!?]*$",
    r"\b(revele|mostre|exiba) (seu|o) (system prompt|prompt de sistema)\b",
    r"\ba partir de agora voce (e|sera)\b",

    r"\b(ignore|disregard) (all )?(previous|prior) (instructions|rules)\b",
    r"\b(ignore|disregard) your (instructions|rules)\b",
    r"\b(show|reveal) (your|the) system prompt\b",
    r"\bfrom now on you (are|will be)\b",
)


def normalize_input(message: str) -> str:
    message = "".join(
        char
        for char in message
        if not unicodedata.category(char).startswith("C")
        or char.isspace()
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
    # Acentos são ignorados apenas na comparação, sem reescrever a pergunta.
    comparison = "".join(
        char
        for char in unicodedata.normalize("NFD", message.casefold())
        if not unicodedata.combining(char)
    )
    return any(
        re.search(pattern, comparison)
        for pattern in PROMPT_INJECTION_PATTERNS
    )
