import hashlib
import json


CACHE_KEY_PREFIX = "agent:answer:v1"


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def build_cache_key(
    *,
    question: str,
    session_id: str | None = None,
    memory_context: str | None = None,
    data_version: str | None = None,
) -> str:

    payload = {
        "question": _normalize_text(question),
        "session_id": session_id or "",
        "memory_context": _normalize_text(memory_context or ""),
        "data_version": data_version or "",
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

    return f"{CACHE_KEY_PREFIX}:{digest}"