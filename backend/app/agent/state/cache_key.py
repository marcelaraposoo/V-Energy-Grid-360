import hashlib
import json


CACHE_KEY_PREFIX = "agent:answer:v6"


def has_data_version(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_cache_key(
    *,
    normalized_question: str,
    data_version: str,
    session_id: str | None = None,
    memory_context: str | None = None,
    user_identity: str | None = None,
) -> str:
    """Recebe a saída normalizada da C1 e o contexto exato enviado ao agente."""
    if not has_data_version(data_version):
        raise ValueError("data_version deve identificar explicitamente o snapshot Gold.")

    scope = hashlib.sha256(json.dumps([session_id, user_identity], separators=(",", ":")).encode()).hexdigest()
    payload = {
        "policy": "semantic-routing-v1",
        "question": normalized_question,
        "session_id": session_id,
        "user_identity": user_identity,
        "memory_context": memory_context,
        "data_version": data_version,
    }
    # Datas relativas e respostas herdadas não podem atravessar o dia de referência.
    from app.agent.context.runtime import reference_date
    payload["reference_date"] = reference_date().isoformat()
    from app.agent.context.knowledge import knowledge_version
    payload["knowledge_version"] = knowledge_version()

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    digest = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

    return f"{CACHE_KEY_PREFIX}:{scope}:{digest}"
