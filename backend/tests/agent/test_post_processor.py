from app.agent.post_processor import (
    MAX_VISUALIZATION_POINTS,
    _humanize_column,
    post_process,
    _infer_unit,
)
from app.agent.schemas import (
    QueryExecutionResult,
    SynthesisResult,
    SynthesisStatus,
    VisualizationType,
)


def _synthesis(
    answer: str = "Resposta aprovada.",
) -> SynthesisResult:
    return SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer=answer,
    )


def _result(
    *,
    columns=None,
    rows=None,
    row_count=None,
    truncated=False,
) -> QueryExecutionResult:
    columns = columns or ["municipio", "receita"]
    rows = rows if rows is not None else [
        ["Recife", 100.0],
        ["Olinda", 80.0],
    ]

    return QueryExecutionResult(
        columns=columns,
        rows=rows,
        row_count=len(rows) if row_count is None else row_count,
        truncated=truncated,
    )


def test_category_and_numeric_metric_generates_bar_chart():
    result = post_process(
        synthesis=_synthesis(),
        result=_result(),
    )

    assert result.visualization is not None
    assert result.visualization.type == VisualizationType.BAR

    assert [
        point.label
        for point in result.visualization.points
    ] == ["Recife", "Olinda"]

    assert [
        point.value
        for point in result.visualization.points
    ] == [100.0, 80.0]


def test_temporal_dimension_generates_line_chart():
    query_result = _result(
        columns=["mes_referencia", "receita"],
        rows=[
            ["2026-01", 100.0],
            ["2026-02", 120.0],
            ["2026-03", 110.0],
        ],
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is not None
    assert result.visualization.type == VisualizationType.LINE


def test_iso_date_dimension_generates_line_chart():
    query_result = _result(
        columns=["data", "consumo_kwh"],
        rows=[
            ["2026-01-01", 100.0],
            ["2026-02-01", 120.0],
        ],
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is not None
    assert result.visualization.type == VisualizationType.LINE


def test_single_row_does_not_generate_visualization():
    query_result = _result(
        rows=[
            ["Recife", 100.0],
        ],
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_empty_result_does_not_generate_visualization():
    query_result = _result(
        columns=["municipio", "receita"],
        rows=[],
        row_count=0,
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_more_than_two_columns_does_not_generate_visualization():
    query_result = _result(
        columns=[
            "municipio",
            "receita",
            "consumo_kwh",
        ],
        rows=[
            ["Recife", 100.0, 200.0],
            ["Olinda", 80.0, 150.0],
        ],
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_non_numeric_metric_does_not_generate_visualization():
    query_result = _result(
        columns=["municipio", "status"],
        rows=[
            ["Recife", "alto"],
            ["Olinda", "baixo"],
        ],
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_truncated_result_does_not_generate_visualization():
    query_result = _result(
        rows=[
            ["Recife", 100.0],
            ["Olinda", 80.0],
        ],
        row_count=50,
        truncated=True,
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_too_many_points_does_not_generate_visualization():
    rows = [
        [f"Municipio {index}", float(index)]
        for index in range(
            MAX_VISUALIZATION_POINTS + 1
        )
    ]

    query_result = _result(
        rows=rows,
    )

    result = post_process(
        synthesis=_synthesis(),
        result=query_result,
    )

    assert result.visualization is None


def test_answer_is_preserved_exactly():
    answer = (
        "A receita cresceu 12,5% no período analisado."
    )

    result = post_process(
        synthesis=_synthesis(answer),
        result=_result(),
    )

    assert result.answer == answer


def test_assumptions_are_preserved():
    synthesis = SynthesisResult(
        status=SynthesisStatus.ANSWERED,
        answer="Resposta.",
        assumptions=[
            "Período considerado: últimos 12 meses."
        ],
    )

    result = post_process(
        synthesis=synthesis,
        result=_result(),
    )

    assert result.assumptions == [
        "Período considerado: últimos 12 meses."
    ]


def test_visualization_uses_query_result_not_synthesis_numbers():
    synthesis = _synthesis(
        "A receita de Recife foi R$ 9999."
    )

    query_result = _result(
        rows=[
            ["Recife", 1000.0],
            ["Olinda", 800.0],
        ],
    )

    result = post_process(
        synthesis=synthesis,
        result=query_result,
    )

    assert result.visualization is not None

    values = [
        point.value
        for point in result.visualization.points
    ]

    assert values == [1000.0, 800.0]
    assert 9999.0 not in values


def test_currency_unit_is_inferred_from_revenue_column():
    result = post_process(
        synthesis=_synthesis(),
        result=_result(
            columns=["municipio", "receita"],
        ),
    )

    assert result.visualization is not None
    assert result.visualization.unit == "R$"


def test_energy_unit_is_inferred():
    result = post_process(
        synthesis=_synthesis(),
        result=_result(
            columns=["municipio", "consumo_kwh"],
        ),
    )

    assert result.visualization is not None
    assert result.visualization.unit == "kWh"


def test_unknown_metric_has_no_unit():
    result = post_process(
        synthesis=_synthesis(),
        result=_result(
            columns=["municipio", "quantidade"],
        ),
    )

    assert result.visualization is not None
    assert result.visualization.unit is None

def test_humanize_known_columns_with_accents():
    assert _humanize_column("mes_referencia") == "Mês de referência"
    assert _humanize_column("municipio") == "Município"

def test_infer_unit_prioritizes_percentage():
    assert _infer_unit("variacao_receita_ano_anterior_pct") == "%"


def test_infer_unit_recognizes_price_per_kwh():
    assert _infer_unit("preco_medio_kwh") == "R$/kWh"


def test_infer_unit_ranking_has_no_unit():
    assert _infer_unit("ranking_dec_mes") is None