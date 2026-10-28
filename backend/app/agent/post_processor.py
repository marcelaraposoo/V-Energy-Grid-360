from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from app.agent.schemas import (
    PostProcessingResult,
    QueryExecutionResult,
    SynthesisResult,
    VisualizationPoint,
    VisualizationSpec,
    VisualizationType,
)


MAX_VISUALIZATION_POINTS = 30

_TEMPORAL_PATTERN = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$"
)

_CURRENCY_TERMS = (
    "receita",
    "faturamento",
    "valor",
)

_ENERGY_TERMS = (
    "consumo",
    "energia",
    "kwh",
)


def _is_number(value: Any) -> bool:

    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float, Decimal)):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _is_temporal(value: Any) -> bool:

    if not isinstance(value, str):
        return False

    return bool(_TEMPORAL_PATTERN.fullmatch(value.strip()))


def _humanize_column(column: str) -> str:


    return column.replace("_", " ").strip().capitalize()


def _infer_unit(metric_column: str) -> str | None:

    name = metric_column.lower()

    if any(term in name for term in _CURRENCY_TERMS):
        return "R$"

    if any(term in name for term in _ENERGY_TERMS):
        return "kWh"

    if "percent" in name or "percentual" in name or name.endswith("_pct"):
        return "%"

    if "dec" in name or "duracao_h" in name or "horas" in name:
        return "h"

    if "fec" in name:
        return "vezes"

    return None


def _build_title(
    visualization_type: VisualizationType,
    label_column: str,
    metric_column: str,
) -> str:
    metric = _humanize_column(metric_column)
    label = _humanize_column(label_column)

    if visualization_type == VisualizationType.LINE:
        return f"Evolução de {metric.lower()} por {label.lower()}"

    return f"{metric} por {label.lower()}"


def _build_visualization(
    result: QueryExecutionResult,
) -> VisualizationSpec | None:

    if result.truncated:
        return None

    if result.row_count <= 1:
        return None

    if len(result.rows) != result.row_count:
        return None

    if len(result.rows) > MAX_VISUALIZATION_POINTS:
        return None

    if len(result.columns) != 2:
        return None

    label_column, metric_column = result.columns

    labels: list[str] = []
    values: list[float] = []

    for row in result.rows:
        if len(row) != 2:
            return None

        label, value = row

        if label is None or not _is_number(value):
            return None

        labels.append(str(label))
        values.append(float(value))

    if not labels:
        return None

    all_temporal = all(_is_temporal(label) for label in labels)

    visualization_type = (
        VisualizationType.LINE
        if all_temporal
        else VisualizationType.BAR
    )

    points = [
        VisualizationPoint(
            label=label,
            value=value,
        )
        for label, value in zip(labels, values, strict=True)
    ]

    return VisualizationSpec(
        type=visualization_type,
        title=_build_title(
            visualization_type,
            label_column,
            metric_column,
        ),
        x_label=_humanize_column(label_column),
        y_label=_humanize_column(metric_column),
        unit=_infer_unit(metric_column),
        points=points,
    )


def post_process(
    synthesis: SynthesisResult,
    result: QueryExecutionResult,
) -> PostProcessingResult:

    visualization = _build_visualization(result)

    return PostProcessingResult(
        answer=synthesis.answer,
        assumptions=list(synthesis.assumptions),
        visualization=visualization,
    )