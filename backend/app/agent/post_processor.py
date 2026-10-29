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

COLUMN_LABELS = {
    "mes_referencia": "Mês de referência",
    "municipio": "Município",
}

_TEMPORAL_PATTERN = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])(?:-\d{2})?$"
)

_UNSAFE_VISUALIZATION_TEXT = re.compile(
    r"(?i)"
    r"(https?://|www\.)"
    r"|(\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b)"
    r"|(\bopenrouter\b|\bgemini\b|\bprovider\b)"
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


def _is_safe_visualization_text(value: str) -> bool:
    text = value.strip()

    if not text:
        return False

    if len(text) > 200:
        return False

    if _UNSAFE_VISUALIZATION_TEXT.search(text):
        return False

    return True


def _humanize_column(column: str) -> str:
    normalized = column.strip().lower()

    if normalized in COLUMN_LABELS:
        return COLUMN_LABELS[normalized]

    return column.replace("_", " ").strip().capitalize()


def _infer_unit(metric_column: str) -> str | None:
    name = metric_column.lower()

    if (
        "percent" in name
        or "percentual" in name
        or name.endswith("_pct")
    ):
        return "%"

    if "preco" in name and "kwh" in name:
        return "R$/kWh"

    if (
        "ranking" in name
        or "qtd" in name
        or "quantidade" in name
    ):
        return None

    if (
        "dec" in name
        or "duracao_h" in name
        or "horas" in name
    ):
        return "h"

    if "fec" in name:
        return "vezes"

    if any(term in name for term in _ENERGY_TERMS):
        return "kWh"

    if any(term in name for term in _CURRENCY_TERMS):
        return "R$"

    return None


def _build_title(
    visualization_type: VisualizationType,
    label_column: str,
    metric_column: str,
) -> str:
    metric = _humanize_column(metric_column)
    label = _humanize_column(label_column)

    if visualization_type == VisualizationType.LINE:
        return (
            f"Evolução de {metric.lower()} "
            f"por {label.lower()}"
        )

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

    if not _is_safe_visualization_text(label_column):
        return None

    if not _is_safe_visualization_text(metric_column):
        return None

    labels: list[str] = []
    values: list[float] = []

    for row in result.rows:
        if len(row) != 2:
            return None

        label, value = row

        if label is None or not _is_number(value):
            return None

        label_text = str(label)

        if not _is_safe_visualization_text(label_text):
            return None

        labels.append(label_text)
        values.append(float(value))

    if not labels:
        return None

    all_temporal = all(
        _is_temporal(label)
        for label in labels
    )

    visualization_type = (
        VisualizationType.LINE
        if all_temporal
        else VisualizationType.BAR
    )

    pairs = list(
        zip(
            labels,
            values,
            strict=True,
        )
    )

    if visualization_type == VisualizationType.LINE:
        pairs.sort(key=lambda item: item[0])

    points = [
        VisualizationPoint(
            label=label,
            value=value,
        )
        for label, value in pairs
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