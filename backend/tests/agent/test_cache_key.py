from app.agent.state.cache_key import (
    CACHE_KEY_PREFIX,
    build_cache_key,
)


def test_same_input_generates_same_key():
    first = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-1",
    )

    assert first == second


def test_question_normalization_keeps_same_key():
    first = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        question="   QUAL   FOI A RECEITA?   ",
        session_id="sessao-1",
    )

    assert first == second


def test_different_question_changes_key():
    first = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        question="Qual foi o consumo?",
        session_id="sessao-1",
    )

    assert first != second


def test_different_session_changes_key():
    first = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-1",
    )

    second = build_cache_key(
        question="Qual foi a receita?",
        session_id="sessao-2",
    )

    assert first != second


def test_different_memory_context_changes_key():
    first = build_cache_key(
        question="E no mês seguinte?",
        session_id="sessao-1",
        memory_context="Pergunta anterior sobre janeiro.",
    )

    second = build_cache_key(
        question="E no mês seguinte?",
        session_id="sessao-1",
        memory_context="Pergunta anterior sobre março.",
    )

    assert first != second


def test_different_data_version_changes_key():
    first = build_cache_key(
        question="Qual foi a receita?",
        data_version="gold-v1",
    )

    second = build_cache_key(
        question="Qual foi a receita?",
        data_version="gold-v2",
    )

    assert first != second


def test_key_does_not_expose_question():
    key = build_cache_key(
        question="Qual foi a receita secreta?",
    )

    assert key.startswith(f"{CACHE_KEY_PREFIX}:")
    assert "receita" not in key
    assert "secreta" not in key