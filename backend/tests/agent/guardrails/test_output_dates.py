from decimal import Decimal

from app.agent.guardrails.allowed_numbers import (
    build_allowed_numbers,
    is_date_supported,
    is_number_supported,
)
from app.agent.guardrails.output_guardrail import (
    build_output_retry_feedback,
    validate_output,
)
from app.agent.guardrails.output_rules import (
    extract_dates,
    extract_numbers,
)
from app.agent.schemas import (
    OutputGuardrailDecision,
    OutputGuardrailReason,
    QueryExecutionResult,
)


PLAIN_SQL = "SELECT municipio, receita FROM kpis_mensal"
PERIOD_SQL = (
    "SELECT municipio, COUNT(*) AS ucs "
    "FROM fato_consumo_faturamento "
    "WHERE mes_referencia = '2026-06' GROUP BY municipio"
)
QUESTION = (
    "Quantas unidades consumidoras ativas por município "
    "em 2026-06?"
)


# ---------------------------------------------------------------
# Extração de datas
# ---------------------------------------------------------------

def _keys(text):
    return [date.key for date in extract_dates(text)]


def test_extracts_iso_month_and_day():
    assert _keys("De 2026-06 até 2026-06-15") == [
        (2026, 6, None),
        (2026, 6, 15),
    ]


def test_extracts_brazilian_full_date():
    assert _keys("Em 15/03/2026 houve") == [(2026, 3, 15)]


def test_extracts_two_digit_year_as_20xx():
    assert _keys("Em 15/03/26 houve") == [(2026, 3, 15)]


def test_extracts_month_and_year():
    assert _keys("Em 03/2026 houve") == [(2026, 3, None)]


def test_full_date_is_not_read_again_as_month_year():
    assert _keys("Em 15/03/2026") == [(2026, 3, 15)]


def test_date_keeps_the_raw_text():
    assert extract_dates("em 03/2026")[0].raw == "03/2026"


def test_text_without_dates():
    assert extract_dates("Recife tem 4.820 unidades.") == []


def test_dates_do_not_become_numbers():
    numbers = extract_numbers("Em 2026-06 e 15/03/2026 foram 1.000")

    assert [number.raw for number in numbers] == ["1.000"]


# ---------------------------------------------------------------
# Datas permitidas
# ---------------------------------------------------------------

def _allowed(rows=None, sql=PLAIN_SQL, question="Pergunta?"):
    rows = rows if rows is not None else [["Recife", 1000]]

    result = QueryExecutionResult(
        columns=[f"c{i}" for i in range(len(rows[0]))],
        rows=rows,
        row_count=len(rows),
    )

    return build_allowed_numbers(question, sql, result)


def _dates_supported(allowed, text):
    dates = extract_dates(text)

    assert dates

    return all(is_date_supported(date, allowed) for date in dates)


def test_month_in_sql_is_supported():
    allowed = _allowed(sql=PERIOD_SQL)

    assert _dates_supported(allowed, "2026-06")
    assert not _dates_supported(allowed, "2025-01")


def test_same_date_in_other_format_is_supported():
    allowed = _allowed(
        sql=PLAIN_SQL + " WHERE data_leitura = '2026-06-15'"
    )

    assert _dates_supported(allowed, "15/06/2026")
    assert _dates_supported(allowed, "15/06/26")


def test_month_is_supported_by_a_day_in_that_month():
    allowed = _allowed(
        sql=PLAIN_SQL + " WHERE data_leitura = '2026-06-15'"
    )

    assert _dates_supported(allowed, "2026-06")
    assert _dates_supported(allowed, "06/2026")


def test_day_is_not_supported_by_a_month_only():
    allowed = _allowed(sql=PERIOD_SQL)

    assert not _dates_supported(allowed, "15/06/2026")
    assert not _dates_supported(allowed, "2026-06-15")


def test_other_day_of_the_same_month_is_not_supported():
    allowed = _allowed(
        sql=PLAIN_SQL + " WHERE data_leitura = '2026-06-15'"
    )

    assert not _dates_supported(allowed, "2026-06-16")


def test_date_only_in_question_is_not_evidence():
    allowed = _allowed(question="Receita em 2025-01?")

    assert not _dates_supported(allowed, "2025-01")


def test_dates_inside_text_cells_are_supported():
    allowed = _allowed(rows=[["2026-06-15 13:20:00", 10]])

    assert _dates_supported(allowed, "15/06/2026")
    assert not _dates_supported(allowed, "16/06/2026")


def test_diagnostic_period_name_in_sql_allows_its_boundaries():
    allowed = _allowed(
        sql=PLAIN_SQL + " WHERE periodo_diagnostico = 'PRIMEIRO_ANO'"
    )

    assert _dates_supported(allowed, "2022-07")
    assert _dates_supported(allowed, "2023-06")
    assert not _dates_supported(allowed, "2023-09")
    assert not _dates_supported(allowed, "2025-07")


def test_diagnostic_period_name_in_cells_allows_its_boundaries():
    allowed = _allowed(
        rows=[["PRIMEIRO_ANO", 10], ["ULTIMOS_12M", 20]]
    )

    for text in ("2022-07", "2023-06", "2025-07", "2026-06"):
        assert _dates_supported(allowed, text)


def test_date_components_are_numeric_evidence():
    allowed = _allowed(sql=PERIOD_SQL)

    assert is_number_supported((Decimal(2026),), allowed)
    assert is_number_supported((Decimal(6),), allowed)
    assert not is_number_supported((Decimal(2025),), allowed)


# ---------------------------------------------------------------
# Guardrail de saída
# ---------------------------------------------------------------

def _result():
    return QueryExecutionResult(
        columns=["municipio", "ucs"],
        rows=[["Recife", 4820], ["Olinda", 1310]],
        row_count=2,
    )


def _validate(
    answer,
    assumptions=None,
    question=QUESTION,
    sql=PERIOD_SQL,
):
    return validate_output(
        answer,
        assumptions or [],
        question,
        sql,
        _result(),
    )


def _is_unsupported(result):
    return (
        result.decision == OutputGuardrailDecision.BLOCK
        and result.reason == OutputGuardrailReason.UNSUPPORTED_NUMBER
    )


def test_allows_date_present_in_sql():
    result = _validate("Em 2026-06, Recife tem 4.820 unidades.")

    assert result.decision == OutputGuardrailDecision.ALLOW


def test_allows_same_month_in_brazilian_format():
    result = _validate("Em 06/2026, Recife tem 4.820 unidades.")

    assert result.decision == OutputGuardrailDecision.ALLOW


def test_blocks_invented_date():
    result = _validate("Em 2025-01, Recife tem 4.820 unidades.")

    assert _is_unsupported(result)
    assert result.unsupported_values == ["2025-01"]


def test_blocks_invented_date_in_brazilian_format():
    result = _validate("Em 15/01/2025, Recife tem 4.820 unidades.")

    assert _is_unsupported(result)
    assert result.unsupported_values == ["15/01/2025"]


def test_blocks_invented_date_in_assumptions():
    result = _validate(
        "Recife tem 4.820 unidades.",
        assumptions=["Período considerado: 2024-03."],
    )

    assert _is_unsupported(result)
    assert result.unsupported_values == ["2024-03"]


def test_blocks_date_taken_only_from_the_question():
    result = _validate(
        "Em 2025-01, Recife tem 4.820 unidades.",
        question="Qual a receita em 2025-01?",
    )

    assert _is_unsupported(result)
    assert result.unsupported_values == ["2025-01"]


def test_reports_numbers_and_dates_together():
    result = _validate("Em 2025-01, Recife tem 9.999 unidades.")

    assert _is_unsupported(result)
    assert result.unsupported_values == ["9.999", "2025-01"]


def test_diagnostic_period_dates_are_allowed_when_sql_names_the_period():
    sql = (
        "SELECT municipio, COUNT(*) AS ucs "
        "FROM fato_consumo_faturamento "
        "WHERE periodo_diagnostico = 'PRIMEIRO_ANO' "
        "GROUP BY municipio"
    )

    result = _validate(
        "No primeiro ano (2022-07 a 2023-06), Recife tem "
        "4.820 unidades.",
        question="Quantas UCs no primeiro ano?",
        sql=sql,
    )

    assert result.decision == OutputGuardrailDecision.ALLOW


def test_blocks_date_outside_the_diagnostic_period():
    sql = (
        "SELECT municipio, COUNT(*) AS ucs "
        "FROM fato_consumo_faturamento "
        "WHERE periodo_diagnostico = 'PRIMEIRO_ANO' "
        "GROUP BY municipio"
    )

    result = _validate(
        "No primeiro ano (2022-07 a 2023-09), Recife tem "
        "4.820 unidades.",
        question="Quantas UCs no primeiro ano?",
        sql=sql,
    )

    assert _is_unsupported(result)
    assert result.unsupported_values == ["2023-09"]


def test_feedback_mentions_the_unsupported_date():
    result = _validate("Em 2025-01, Recife tem 4.820 unidades.")

    feedback = build_output_retry_feedback(result)

    assert feedback is not None
    assert "2025-01" in feedback