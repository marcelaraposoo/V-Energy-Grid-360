import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    PostProcessingResult,
    VisualizationPoint,
    VisualizationSpec,
    VisualizationType,
)


def test_valid_visualization_spec():
    visualization = VisualizationSpec(
        type=VisualizationType.BAR,
        title="Receita por município",
        x_label="Município",
        y_label="Receita",
        unit="R$",
        points=[
            VisualizationPoint(
                label="Recife",
                value=100.0,
            ),
            VisualizationPoint(
                label="Olinda",
                value=80.0,
            ),
        ],
    )

    assert visualization.type == VisualizationType.BAR
    assert len(visualization.points) == 2
    assert visualization.unit == "R$"


def test_visualization_accepts_optional_labels_and_unit():
    visualization = VisualizationSpec(
        type=VisualizationType.LINE,
        title="Evolução mensal",
        points=[
            VisualizationPoint(
                label="2026-01",
                value=100.0,
            ),
            VisualizationPoint(
                label="2026-02",
                value=120.0,
            ),
        ],
    )

    assert visualization.x_label is None
    assert visualization.y_label is None
    assert visualization.unit is None


@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
        "\n",
    ],
)
def test_visualization_rejects_empty_title(title):
    with pytest.raises(ValidationError):
        VisualizationSpec(
            type=VisualizationType.BAR,
            title=title,
            points=[
                VisualizationPoint(
                    label="Recife",
                    value=100.0,
                )
            ],
        )


def test_visualization_rejects_empty_points():
    with pytest.raises(ValidationError):
        VisualizationSpec(
            type=VisualizationType.BAR,
            title="Receita por município",
            points=[],
        )


def test_valid_post_processing_result_without_visualization():
    result = PostProcessingResult(
        answer="Existem 328 faturas em aberto.",
    )

    assert result.answer == (
        "Existem 328 faturas em aberto."
    )
    assert result.assumptions == []
    assert result.visualization is None


def test_valid_post_processing_result_with_visualization():
    visualization = VisualizationSpec(
        type=VisualizationType.BAR,
        title="Receita por município",
        points=[
            VisualizationPoint(
                label="Recife",
                value=100.0,
            ),
            VisualizationPoint(
                label="Olinda",
                value=80.0,
            ),
        ],
    )

    result = PostProcessingResult(
        answer="Recife possui a maior receita.",
        assumptions=[
            "Período considerado: últimos 12 meses."
        ],
        visualization=visualization,
    )

    assert result.visualization == visualization
    assert result.assumptions == [
        "Período considerado: últimos 12 meses."
    ]


@pytest.mark.parametrize(
    "answer",
    [
        "",
        "   ",
        "\n",
    ],
)
def test_post_processing_rejects_empty_answer(answer):
    with pytest.raises(ValidationError):
        PostProcessingResult(
            answer=answer,
        )


def test_visualization_point_accepts_negative_values():
    point = VisualizationPoint(
        label="Variação",
        value=-15.5,
    )

    assert point.value == -15.5


def test_visualization_point_accepts_zero():
    point = VisualizationPoint(
        label="Sem ocorrência",
        value=0.0,
    )

    assert point.value == 0.0