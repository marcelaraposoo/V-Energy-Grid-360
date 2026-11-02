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

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")

_NO_UNIT_TOKENS = {
    "atipica", "corrigido", "explicada", "aberto", "possui",
    "troca", "ranking", "prioridade", "score", "qtd",
    "quantidade", "posicao", "nota", "ano", "mes",
}

_READABLE = {
    "mes_referencia": "Mês de referência",
    "municipio": "Município",
    "bairro": "Bairro",
    "classe": "Classe",
    "alimentador": "Alimentador",
    "receita": "Receita",
    "receita_energia": "Receita de energia",
    "receita_total": "Receita total",
    "consumo_kwh": "Consumo",
    "dec_horas": "DEC",
    "fec": "FEC",
    "qtd_ucs": "Quantidade de UCs",
    "variacao_receita": "Variação de receita",
    "efeito_preco": "Efeito preço",
    "efeito_volume": "Efeito volume",
}

_TEMPORAL_PATTERN = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?$"
)

_UNSAFE_VISUALIZATION_TEXT = re.compile(
    r"(?i)"
    r"(https?://|www\.)"
    r"|(\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b)"
    r"|(\bopenrouter\b|\bgemini\b|\bprovider\b)"
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
    known = _READABLE.get(column.lower())

    if known:
        return known

    return column.replace("_", " ").strip().capitalize()


def _infer_unit(metric_column: str) -> str | None:
    tokens = {
        t for t in _TOKEN_SPLIT.split(metric_column.lower()) if t
    }

    # Percentual vem antes de tudo: "variacao_receita_pct" é %.
    if tokens & {"pct", "percent", "percentual"}:
        return "%"

    # "valor_em_aberto" é dinheiro; só o booleano "em_aberto" não tem unidade.
    if "valor" in tokens:
        return "R$"

    if tokens & _NO_UNIT_TOKENS:
        return None

    if "preco" in tokens and ("kwh" in tokens or "medio" in tokens):
        return "R$/kWh"

    if tokens & {
        "receita", "faturamento", "valor", "tributos",
        "efeito", "variacao_receita",
    }:
        return "R$"

    if "min" in tokens:
        return "min"

    if tokens & {"dec", "horas", "interrompidas"}:
        return "h"

    if "fec" in tokens:
        return "vezes"

    if tokens & {"consumo", "energia", "kwh", "volume"}:
        return "kWh"

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

    pairs = list(zip(labels, values, strict=True))

    if visualization_type == VisualizationType.LINE:
        pairs.sort(key=lambda pair: pair[0])

    points = [
        VisualizationPoint(label=label, value=value)
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