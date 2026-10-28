import re
from functools import lru_cache

from app.agent.prompts.sql_generation.loader import (
    load_sql_generation_prompts,
)
from app.agent.prompts.synthesis.loader import (
    load_synthesis_prompts,
)
from app.core.config import settings


MAX_ANSWER_LENGTH = 3000
MIN_PROMPT_FRAGMENT_LENGTH = 40
MIN_SQL_ECHO_LENGTH = 20


URL_PATTERN = re.compile(
    r"(?<!\w)(?:https?://|ftp://|www\.)\S+",
    flags=re.IGNORECASE,
)


SQL_PATTERNS = tuple(
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"\bSELECT\b[\s\S]*?\bFROM\b",
        r"\bINSERT\s+INTO\b",
        r"\bUPDATE\b[\s\S]*?\bSET\b",
        r"\bDELETE\s+FROM\b",
        r"\b(?:DROP|ALTER|CREATE|TRUNCATE)\s+"
        r"(?:TABLE|DATABASE|VIEW)\b",
        r"\bGROUP\s+BY\b",
        r"\bORDER\s+BY\b",
        r"\bJOIN\b[\s\S]{0,80}?\bON\b",
    )
)


PROMPT_MARKER_PATTERNS = tuple(
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"</?\s*(?:user_question|executed_sql|query_result|"
        r"conversation_context|database_context|"
        r"guardrail_feedback)\s*>",
        r"\bsystem\s+prompt\b",
        r"\bprompt\s+de\s+sistema\b",
        r"\binstru[çc][õo]es\s+(?:internas|do\s+sistema)\b",
        r"(?m)^\s*#{1,3}\s*(?:Papel|Segurança|"
        r"Contrato de Saída|Regras de fidelidade)\b",
    )
)


STATIC_PROVIDER_PATTERN = re.compile(
    r"(?<![\w-])(?:gemini|gemma|nemotron|openrouter|nvidia|"
    r"pydantic(?:\s?ai)?|openai|anthropic|claude|llama|mistral|"
    r"google\s+ai\s+studio)(?!\w)",
    flags=re.IGNORECASE,
)


TECHNICAL_ERROR_PATTERNS = (
    re.compile(
        r"Traceback \(most recent call last\)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r'File\s+"[^"]+",\s+line\s+\d+',
        flags=re.IGNORECASE,
    ),
    # Nomes de exceção (ValueError, ModelHTTPError...).
    # Case-sensitive de propósito, para não pegar "erro".
    re.compile(r"\b[A-Z][A-Za-z]*(?:Error|Exception)\b"),
    re.compile(
        r"\bstatus[_ ]?code\s*[:=]\s*\d{3}\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\bHTTP\s*[45]\d{2}\b", flags=re.IGNORECASE),
    re.compile(r"\bsqlite3\.\w+", flags=re.IGNORECASE),
    re.compile(
        r"\bno such (?:table|column)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\bsyntax error\b", flags=re.IGNORECASE),
    re.compile(r"\bat 0x[0-9a-f]+\b", flags=re.IGNORECASE),
    re.compile(r"\bNoneType\b"),
    re.compile(r"\b[\w./\\-]+\.py\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:app|backend)[/\\][\w./\\-]+",
        flags=re.IGNORECASE,
    ),
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _normalize_fragment(text: str) -> str:
    text = re.sub(r"[*`#>]", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text)

    return _collapse(text)


def lacks_useful_content(answer: str) -> bool:
    return not any(char.isalnum() for char in answer)


def exceeds_max_length(answer: str) -> bool:
    return len(answer) > MAX_ANSWER_LENGTH


def contains_url(text: str) -> bool:
    return bool(URL_PATTERN.search(text))


def contains_sql(text: str) -> bool:
    return any(
        pattern.search(text) for pattern in SQL_PATTERNS
    )


def echoes_executed_sql(text: str, sql: str) -> bool:
    normalized_sql = _collapse(sql).rstrip("; ")

    if len(normalized_sql) < MIN_SQL_ECHO_LENGTH:
        return False

    return normalized_sql in _collapse(text)


def contains_technical_error(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in TECHNICAL_ERROR_PATTERNS
    )


def _configured_model_terms() -> tuple[str, ...]:
    """
    Nomes dos modelos lidos da configuração, para a lista não
    ficar desatualizada se o time trocar de modelo.
    """

    names = [
        getattr(settings, "gemini_model", None),
        *getattr(settings, "openrouter_models", []),
    ]

    terms: list[str] = []

    for name in names:
        if not name:
            continue

        terms.append(name)
        terms.append(name.split("/")[-1].split(":")[0])

    return tuple(
        dict.fromkeys(
            term.lower() for term in terms if len(term) >= 4
        )
    )


def mentions_provider_or_model(text: str) -> bool:
    if STATIC_PROVIDER_PATTERN.search(text):
        return True

    lowered = text.lower()

    return any(
        term in lowered for term in _configured_model_terms()
    )


@lru_cache(maxsize=1)
def _prompt_fragments() -> tuple[str, ...]:
    """
    Linhas longas dos prompts internos, normalizadas.
    Se uma delas aparecer na resposta, o prompt vazou.
    """

    prompts = "\n".join(
        (
            load_synthesis_prompts(),
            load_sql_generation_prompts(),
        )
    )

    fragments = [
        fragment
        for fragment in (
            _normalize_fragment(line)
            for line in prompts.splitlines()
        )
        if len(fragment) >= MIN_PROMPT_FRAGMENT_LENGTH
    ]

    return tuple(dict.fromkeys(fragments))


def leaks_prompt(text: str) -> bool:
    if any(
        pattern.search(text)
        for pattern in PROMPT_MARKER_PATTERNS
    ):
        return True

    normalized = _normalize_fragment(text)

    return any(
        fragment in normalized
        for fragment in _prompt_fragments()
    )