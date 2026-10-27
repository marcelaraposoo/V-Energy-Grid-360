from decimal import Decimal

from app.agent.answer_synthesizer import MAX_ROWS_IN_PROMPT
from app.agent.guardrails.allowed_numbers import (
    MAX_ROWS_SHOWN,
    build_allowed_numbers,
    is_number_supported,
)
from app.agent.schemas import QueryExecutionResult


def _result(rows, row_count=None, truncated=False):
    columns = [f"c{i}" for i in range(len(rows[0]))]

    return QueryExecutionResult(
        columns=columns,
        rows=rows,
        row_count=(
            row_count if row_count is not None else len(rows)
        ),
        truncated=truncated,
    )


def _allowed(rows, question="Pergunta?", sql="SELECT 1", **kwargs):
    return build_allowed_numbers(
        question, sql, _result(rows, **kwargs)
    )


def _supported(allowed, *tokens):
    return all(
        is_number_supported((Decimal(token),), allowed)
        for token in tokens
    )


def test_max_rows_matches_synthesizer_limit():
    assert MAX_ROWS_SHOWN == MAX_ROWS_IN_PROMPT


def test_row_values_are_supported():
    allowed = _allowed([["Recife", 4820], ["Olinda", 1310]])

    assert _supported(allowed, "4820", "1310")


def test_sum_is_supported_when_result_is_complete():
    allowed = _allowed([["Recife", 4820], ["Olinda", 1310]])

    assert allowed.derived_enabled is True
    assert _supported(allowed, "6130")


def test_mean_min_max_and_count_are_supported():
    allowed = _allowed([["a", 100], ["b", 200], ["c", 300]])

    assert _supported(allowed, "200", "100", "300", "600")


def test_share_of_total_is_supported_with_rounding():
    allowed = _allowed([["a", 100], ["b", 200]])

    assert _supported(allowed, "33.3", "66.7")


def test_fabricated_number_is_not_supported():
    allowed = _allowed([["Recife", 4820], ["Olinda", 1310]])

    assert not _supported(allowed, "9999")


def test_derived_values_disabled_when_truncated():
    allowed = _allowed(
        [["Recife", 4820], ["Olinda", 1310]],
        row_count=500,
        truncated=True,
    )

    assert allowed.derived_enabled is False
    assert _supported(allowed, "4820", "1310", "500")
    assert not _supported(allowed, "6130")


def test_derived_values_disabled_when_row_count_exceeds_rows():
    allowed = _allowed(
        [["Recife", 4820], ["Olinda", 1310]],
        row_count=80,
        truncated=True,
    )

    assert allowed.derived_enabled is False
    assert not _supported(allowed, "6130")


def test_rows_beyond_prompt_limit_are_not_allowed():
    rows = [[f"m{i}", i * 1000] for i in range(60)]

    allowed = _allowed(rows)

    assert allowed.derived_enabled is False
    assert _supported(allowed, "49000")
    assert not _supported(allowed, "55000")


def test_numbers_from_question_and_sql_are_supported():
    allowed = _allowed(
        [["a", 1000]],
        question="Quais os 77 maiores?",
        sql="SELECT * FROM t LIMIT 31",
    )

    assert _supported(allowed, "77", "31")


def test_date_components_are_supported():
    allowed = _allowed(
        [["a", 1000]],
        question="Receita em 2026-06",
    )

    assert _supported(allowed, "2026", "6")
    assert not _supported(allowed, "2025")


def test_numbers_inside_text_cells_are_supported():
    allowed = _allowed([["Bairro 25", 125]])

    assert _supported(allowed, "25", "125")


def test_dates_inside_text_cells_are_supported():
    allowed = _allowed([["2026-06", 1000]])

    assert _supported(allowed, "2026", "6")


def test_none_cells_are_ignored():
    allowed = _allowed([["x", None], ["y", 50]])

    assert _supported(allowed, "50")


def test_float_values_match_with_rounding_tolerance():
    allowed = _allowed([["x", 79.63]])

    assert _supported(allowed, "79.6")
    assert not _supported(allowed, "79.7")


def test_ambiguous_token_matches_any_interpretation():
    candidates = (Decimal("4820"), Decimal("4.820"))

    assert is_number_supported(
        candidates, _allowed([["a", 4820]])
    )
    assert is_number_supported(
        candidates, _allowed([["a", 4.82]])
    )
    assert not is_number_supported(
        candidates, _allowed([["a", 1310]])
    )


def test_sign_is_ignored():
    allowed = _allowed([["x", -52]])

    assert _supported(allowed, "52")


def test_constants_are_supported():
    allowed = _allowed([["a", 1000]])

    assert _supported(allowed, "12", "100", "0", "1")


def test_positions_up_to_row_count_are_supported():
    allowed = _allowed(
        [["a", 1000], ["b", 2000], ["c", 3000], ["d", 4000]]
    )

    assert _supported(allowed, "2")
    assert not _supported(allowed, "5")


def test_number_without_interpretation_is_not_supported():
    allowed = _allowed([["a", 1000]])

    assert not is_number_supported((), allowed)