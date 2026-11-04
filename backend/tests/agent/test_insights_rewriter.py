import asyncio

import pytest

from app.agent.insights import rewriter
from app.agent.insights.rewriter import (
    is_faithful,
    numbers_are_supported,
    sanitize,
)
from app.schemas import Insight

DADOS = {
    "variacao_receita": -123456.789,
    "efeito_preco": 5000.0,
    "variacao_energia_pct": -3.7,
    "chave": "Recife",
}


def _insight():
    return Insight(tipo="alerta", dados=DADOS, texto="Texto das regras.")


@pytest.mark.parametrize(
    "text",
    [
        "A receita variou R$ 123.456,79.",
        "A receita variou R$ 123.457.",
        "A energia caiu 3,7%.",
        "O efeito de preço foi de R$ 5.000.",
    ],
)
def test_supported_numbers_pass(text):
    assert numbers_are_supported(text, DADOS)


@pytest.mark.parametrize(
    "text",
    [
        "A receita variou R$ 999.999.",
        "A energia caiu 37%.",
    ],
)
def test_invented_numbers_fail(text):
    assert not numbers_are_supported(text, DADOS)


def test_dates_are_not_numbers():
    assert numbers_are_supported("No mês 2026-06 houve alta.", DADOS) is True


def test_feeder_codes_are_not_numbers():
    dados = {"dec_horas": 11.208333}
    assert numbers_are_supported(
        "O alimentador AL025 registrou DEC de 11,21 h.", dados
    )
    assert numbers_are_supported(
        "O alimentador ALM-JAB-015 registrou DEC de 11,21 h.", dados
    )


def test_negative_numbers_are_still_checked():
    assert not numbers_are_supported("A queda foi de -9,9%.", {"x": -3.7})


@pytest.mark.parametrize(
    "text",
    [
        "Veja https://exemplo.com",
        "Gerado pelo Gemini.",
        "SELECT * FROM dim_uc",
        "",
        "x" * 400,
    ],
)
def test_unsafe_text_is_rejected(text):
    assert not is_faithful(text, DADOS)


def test_sensitive_keys_are_removed():
    clean = sanitize({"uc_id": "UC1", "x": 1, "n": [{"cep": "5", "y": 2}]})
    assert clean == {"x": 1, "n": [{"y": 2}]}


def _patch(monkeypatch, output=None, error=None, delay=0.0):
    async def fake(prompt, **kwargs):
        if delay:
            await asyncio.sleep(delay)
        return output, [], error

    monkeypatch.setattr(rewriter, "run_with_fallback", fake)
    monkeypatch.setenv("INSIGHTS_LLM", "1")


def test_disabled_by_default_keeps_text(monkeypatch):
    monkeypatch.delenv("INSIGHTS_LLM", raising=False)
    result = rewriter.rewrite_insights([_insight()])
    assert result[0].texto == "Texto das regras."


def test_valid_rewrite_is_used(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7% em Recife.")
    assert rewriter.rewrite_insights([_insight()])[0].texto == (
        "A energia caiu 3,7% em Recife."
    )


def test_invented_number_falls_back(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 40%.")
    assert rewriter.rewrite_insights([_insight()])[0].texto == "Texto das regras."


def test_provider_error_falls_back(monkeypatch):
    _patch(monkeypatch, error="timeout")
    assert rewriter.rewrite_insights([_insight()])[0].texto == "Texto das regras."


def test_timeout_falls_back(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7%.", delay=1)
    monkeypatch.setattr(rewriter, "TIMEOUT_SECONDS", 0.05)
    assert rewriter.rewrite_insights([_insight()])[0].texto == "Texto das regras."


def test_type_and_data_are_preserved(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7%.")
    result = rewriter.rewrite_insights([_insight()])[0]
    assert result.tipo == "alerta" and result.dados == DADOS
