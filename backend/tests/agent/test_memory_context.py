from app.agent.schemas import AgentOutcome, MemoryEntry
from app.agent.state.memory_context import (
    MEMORY_CONTEXT_LIMIT,
    MEMORY_CONTEXT_MAX_CHARS,
    MEMORY_STORAGE_LIMIT,
    build_memory_context,
)


def _entry(number: int) -> MemoryEntry:
    return MemoryEntry(
        question=f"Pergunta {number}",
        answer=f"Resposta {number}",
        outcome=AgentOutcome.ANSWERED,
    )


def test_empty_memory_returns_none():
    assert build_memory_context([]) is None


def test_builds_context_from_entries():
    context = build_memory_context(
        [
            _entry(1),
            _entry(2),
        ]
    )

    assert context == (
        "Usuário: Pergunta 1\n"
        "Assistente: Resposta 1\n\n"
        "Usuário: Pergunta 2\n"
        "Assistente: Resposta 2"
    )


def test_uses_only_last_five_entries():
    entries = [
        _entry(number)
        for number in range(1, 8)
    ]

    context = build_memory_context(entries)

    assert context is not None

    assert "Pergunta 1" not in context
    assert "Pergunta 2" not in context

    for number in range(3, 8):
        assert f"Pergunta {number}" in context


def test_memory_context_limit_is_five():
    assert MEMORY_CONTEXT_LIMIT == 5


def test_memory_storage_limit_is_twenty():
    assert MEMORY_STORAGE_LIMIT == 20


def test_storage_limit_is_greater_than_context_limit():
    assert MEMORY_STORAGE_LIMIT > MEMORY_CONTEXT_LIMIT

def test_memory_context_respects_character_limit():
    entries = [
        MemoryEntry(
            question=f"Pergunta {number}",
            answer="x" * 1500,
            outcome=AgentOutcome.ANSWERED,
        )
        for number in range(1, 6)
    ]

    context = build_memory_context(entries)

    assert context is not None
    assert len(context) <= MEMORY_CONTEXT_MAX_CHARS


def test_memory_context_prioritizes_most_recent_entries():
    entries = [
        MemoryEntry(
            question=f"Pergunta {number}",
            answer="x" * 1500,
            outcome=AgentOutcome.ANSWERED,
        )
        for number in range(1, 6)
    ]

    context = build_memory_context(entries)

    assert context is not None
    assert "Pergunta 5" in context