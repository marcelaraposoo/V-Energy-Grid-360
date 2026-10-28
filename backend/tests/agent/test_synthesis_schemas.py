import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
)


def test_valid_query_result():
    result = QueryExecutionResult(
        columns=["municipio", "receita"],
        rows=[["Recife", 100.0], ["Olinda", 50.0]],
        row_count=2,
    )

    assert result.truncated is False
    assert len(result.rows) == 2


def test_empty_query_result_is_valid():
    result = QueryExecutionResult(
        columns=["municipio"],
        rows=[],
        row_count=0,
    )

    assert result.rows == []


def test_truncated_result_may_have_fewer_rows_than_row_count():
    result = QueryExecutionResult(
        columns=["municipio"],
        rows=[["Recife"]],
        row_count=500,
        truncated=True,
    )

    assert result.truncated is True


def test_rejects_negative_row_count():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a"],
            rows=[],
            row_count=-1,
        )


def test_rejects_more_rows_than_row_count():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a"],
            rows=[[1], [2]],
            row_count=1,
        )


def test_rejects_row_with_wrong_number_of_values():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a", "b"],
            rows=[[1]],
            row_count=1,
        )


def test_valid_synthesis_result():
    result = SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer="A receita de Recife foi de R$ 100,00.",
        assumptions=["Período considerado: últimos 12 meses."],
    )

    assert result.assumptions == [
        "Período considerado: últimos 12 meses."
    ]


def test_synthesis_assumptions_default_to_empty_list():
    result = SynthesisResult(
        status=SynthesisStatus.NO_DATA,
        answer="Não encontrei dados para esse filtro.",
    )

    assert result.assumptions == []


@pytest.mark.parametrize("answer", ["", "   ", "\n"])
def test_rejects_empty_answer(answer):
    with pytest.raises(ValidationError):
        SynthesisResult(
            status=SynthesisStatus.ANSWERED,
            answer=answer,
        )


def test_rejects_row_count_greater_than_rows_without_truncation():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a"],
            rows=[[1]],
            row_count=500,
        )


def test_rejects_explicit_untruncated_result_with_missing_rows():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a"],
            rows=[[1]],
            row_count=500,
            truncated=False,
        )


def test_rejects_non_empty_row_count_with_no_rows_and_no_truncation():
    with pytest.raises(ValidationError):
        QueryExecutionResult(
            columns=["a"],
            rows=[],
            row_count=3,
        )


def test_truncated_result_with_all_rows_is_valid():
    result = QueryExecutionResult(
        columns=["a"],
        rows=[[1], [2]],
        row_count=2,
        truncated=True,
    )

    assert result.truncated is True