from app.agent.schemas import MemoryEntry


MEMORY_STORAGE_LIMIT = 20
MEMORY_CONTEXT_LIMIT = 5
MEMORY_CONTEXT_MAX_CHARS = 4000


def _format_entry(entry: MemoryEntry) -> str:
    return (
        f"Usuário: {entry.question}\n"
        f"Assistente: {entry.answer}"
    )


def build_memory_context(
    entries: list[MemoryEntry],
) -> str | None:

    if not entries:
        return None

    recent_entries = entries[-MEMORY_CONTEXT_LIMIT:]

    selected: list[str] = []
    total_chars = 0

    # Percorre da interação mais recente para a mais antiga,
    # priorizando sempre o contexto mais próximo da pergunta atual.
    for entry in reversed(recent_entries):
        formatted = _format_entry(entry)

        separator_size = 2 if selected else 0
        required_chars = len(formatted) + separator_size

        if total_chars + required_chars > MEMORY_CONTEXT_MAX_CHARS:
            continue

        selected.append(formatted)
        total_chars += required_chars

    if not selected:
        return None

    selected.reverse()

    return "\n\n".join(selected)