from decimal import Decimal

import pytest

from app.agent.guardrails.output_rules import (
    extract_numbers,
    parse_number_token,
)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("4820", {Decimal("4820")}),
        ("1.234,56", {Decimal("1234.56")}),
        ("1,234.56", {Decimal("1234.56")}),
        ("12,5", {Decimal("12.5")}),
        ("12.5", {Decimal("12.5")}),
        ("0,500", {Decimal("0.5")}),
        ("0.5", {Decimal("0.5")}),
        ("1.234.567", {Decimal("1234567")}),
        ("1,234,567", {Decimal("1234567")}),
    ],
)
def test_parses_unambiguous_tokens(token, expected):
    assert set(parse_number_token(token)) == expected


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("4.820", {Decimal("4820"), Decimal("4.82")}),
        ("1.000", {Decimal("1000"), Decimal("1")}),
        ("12,345", {Decimal("12345"), Decimal("12.345")}),
    ],
)
def test_ambiguous_tokens_keep_both_interpretations(
    token, expected
):
    assert set(parse_number_token(token)) == expected


@pytest.mark.parametrize(
    "token",
    ["1.2.3", "12.34.56", "1.234,5.6"],
)
def test_malformed_tokens_have_no_interpretation(token):
    assert parse_number_token(token) == ()


def test_preserves_written_decimal_places():
    assert (
        parse_number_token("79,6")[0].as_tuple().exponent == -1
    )
    assert (
        parse_number_token("4820")[0].as_tuple().exponent == 0
    )


def _raws(text):
    return [number.raw for number in extract_numbers(text)]


def test_extracts_numbers_from_real_answer():
    text = (
        "Atualmente, existem 6.130 unidades consumidoras "
        "ativas: Recife conta com 4.820 unidades e "
        "Olinda com 1.310."
    )

    assert _raws(text) == ["6.130", "4.820", "1.310"]


def test_sentence_final_period_is_not_part_of_number():
    assert _raws("Foram 1.310.") == ["1.310"]


def test_extracts_currency_and_percentage():
    assert _raws("Receita de R$ 1.234,56") == ["1.234,56"]
    assert _raws("Queda de 12,5%") == ["12,5"]


def test_sign_is_ignored():
    assert _raws("Variação de -5,2%") == ["5,2"]


def test_ranges_are_two_numbers():
    assert _raws("Entre 100-200 kWh") == ["100", "200"]


def test_ignores_iso_periods():
    text = "No período 2026-06, a receita foi de 1.000."

    assert _raws(text) == ["1.000"]


def test_ignores_full_dates_and_month_year():
    assert _raws("Em 15/03/2026 houve 5 casos") == ["5"]
    assert _raws("Em 03/2026 houve 7 casos") == ["7"]


def test_ignores_identifiers_with_digits():
    assert _raws("Classes B1 e A4") == []


def test_ignores_list_markers():
    text = "1. Recife: 4.820\n2. Olinda: 1.310"

    assert _raws(text) == ["4.820", "1.310"]


def test_number_at_line_start_is_not_a_list_marker():
    assert _raws("4.820 unidades") == ["4.820"]


def test_keeps_numbers_inside_labels():
    text = "Bairro 25 registra 125 kWh"

    assert _raws(text) == ["25", "125"]


def test_malformed_number_is_extracted_without_candidates():
    numbers = extract_numbers("versão 1.2.3")

    assert [n.raw for n in numbers] == ["1.2.3"]
    assert numbers[0].candidates == ()


def test_text_without_numbers():
    assert extract_numbers("Sem valores aqui.") == []
    assert extract_numbers("") == []