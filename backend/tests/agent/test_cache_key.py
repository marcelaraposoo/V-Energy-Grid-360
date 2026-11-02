import pytest

from app.agent.guardrails.input_guardrail import validate_input
from app.agent.state.cache_key import (
    CACHE_KEY_PREFIX,
    build_cache_key,
)


def test_same_input_generates_same_key():
    first = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
    )

    assert first == second


def test_question_normalization_is_provided_by_c1():
    normalized = validate_input("   Qual\rfoi   a receita?   ").normalized_input
    first = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        data_version="gold-v1",
        normalized_question=normalized,
        session_id="sessao-1",
    )

    assert first == second


def test_different_question_changes_key():
    first = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi o consumo?",
        session_id="sessao-1",
    )

    assert first != second


def test_different_session_changes_key():
    first = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita?",
        session_id="sessao-2",
    )

    assert first != second


def test_different_memory_context_changes_key():
    first = build_cache_key(
        data_version="gold-v1",
        normalized_question="E no mês seguinte?",
        session_id="sessao-1",
        memory_context="Pergunta anterior sobre janeiro.",
    )

    second = build_cache_key(
        data_version="gold-v1",
        normalized_question="E no mês seguinte?",
        session_id="sessao-1",
        memory_context="Pergunta anterior sobre março.",
    )

    assert first != second


def test_different_data_version_changes_key():
    first = build_cache_key(
        normalized_question="Qual foi a receita?",
        data_version="gold-v1",
    )

    second = build_cache_key(
        normalized_question="Qual foi a receita?",
        data_version="gold-v2",
    )

    assert first != second


def test_key_does_not_expose_question():
    key = build_cache_key(
        data_version="gold-v1",
        normalized_question="Qual foi a receita secreta?",
        session_id="sessao-secreta-123",
        memory_context="contexto confidencial",
    )

    assert key.startswith(f"{CACHE_KEY_PREFIX}:")
    assert "receita" not in key
    assert "secreta" not in key
    assert "sessao-secreta-123" not in key
    assert "confidencial" not in key
    digest = key.removeprefix(f"{CACHE_KEY_PREFIX}:")
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)


@pytest.mark.parametrize("field", ["normalized_question", "memory_context"])
def test_cache_key_preserves_literal_case(field):
    values = dict(normalized_question="E Recife?", data_version="gold-v1")
    values[field] = "Filtro exato 'WEB'"
    first = build_cache_key(**values)
    values[field] = "Filtro exato 'web'"

    assert first != build_cache_key(**values)


def test_cache_key_preserves_effective_memory_whitespace():
    values = dict(normalized_question="E Recife?", data_version="gold-v1")

    assert build_cache_key(**values, memory_context="A\nB") != build_cache_key(
        **values, memory_context="A B"
    )


@pytest.mark.parametrize("version", [None, "", "   "])
def test_cache_key_requires_snapshot_version(version):
    with pytest.raises(ValueError, match="data_version"):
        build_cache_key(normalized_question="Receita?", data_version=version)
