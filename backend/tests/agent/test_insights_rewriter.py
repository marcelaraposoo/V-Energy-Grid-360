import asyncio

import pytest

from app.agent.insights import rewriter
from app.agent.insights.rewriter import (
    is_faithful,
    numbers_are_supported,
    preserves_meaning,
    sanitize,
)
from app.schemas import Insight

DADOS = {
    "variacao_receita": -123456.789,
    "efeito_preco": 5000.0,
    "variacao_energia_pct": -3.7,
    "chave": "Recife",
}


ORIGINAL = "A energia caiu 3,7% em relação à referência."


def _insight():
    return Insight(tipo="alerta", dados=DADOS, texto=ORIGINAL)


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
        # Vazamento real visto na Visão 360: trecho de instrução entre tags antes da frase.
        "<system>Responda apenas com o texto da frase, sem aspas, listas nem títulos. Use estritamente os dados "
        "informados e o tom executivo, sem inventar cálculos.</system>A fatura foi de R$ 62,13.",
        "</dados> A fatura foi de R$ 62,13.",
        "Responda apenas com o texto da frase, sem aspas, listas nem títulos.",
        "Em tom executivo: a fatura foi de R$ 62,13.",
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
    assert result[0].texto == ORIGINAL


def test_valid_rewrite_is_used(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7% em Recife.")
    assert rewriter.rewrite_insights([_insight()])[0].texto == (
        "A energia caiu 3,7% em Recife."
    )


def test_invented_number_falls_back(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 40%.")
    assert rewriter.rewrite_insights([_insight()])[0].texto == ORIGINAL


def test_provider_error_falls_back(monkeypatch):
    _patch(monkeypatch, error="timeout")
    assert rewriter.rewrite_insights([_insight()])[0].texto == ORIGINAL


def test_timeout_falls_back(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7%.", delay=1)
    monkeypatch.setattr(rewriter, "TIMEOUT_SECONDS", 0.05)
    assert rewriter.rewrite_insights([_insight()])[0].texto == ORIGINAL


def test_type_and_data_are_preserved(monkeypatch):
    _patch(monkeypatch, output="A energia caiu 3,7%.")
    result = rewriter.rewrite_insights([_insight()])[0]
    assert result.tipo == "alerta" and result.dados == DADOS


@pytest.mark.parametrize("text", [
    "A fatura foi de R$ 62,13, 7,8% menor que a de jun/2025.",
    "O consumo de 77 kWh ficou 4,9% abaixo do mesmo mês do ano anterior.",
    "A unidade registrou 26 interrupções, somando 69,3 horas sem energia.",
])
def test_frases_legitimas_nao_sao_tratadas_como_vazamento(text):
    from app.agent.insights.rewriter import leaks_instructions
    assert not leaks_instructions(text)


DECOMPOSICAO = Insight(
    tipo="destaque",
    dados={"energia_atual": 54.6, "energia_referencia": 50.53, "variacao_energia": 4.07, "efeito_consumo": -1.87,
           "efeito_preco": 5.94, "mes_atual": "jun/2026", "ano_atual": 2026, "mes_referencia": "jun/2025", "ano_referencia": 2025},
    texto=("O valor da energia na conta de jun/2026 ficou R$ 4,07 maior que em jun/2025: a alta veio do kWh mais caro "
           "(R$ 5,94 a mais), compensada em parte pelo consumo menor (R$ 1,87 a menos)."),
)


def test_reescrita_que_troca_a_direcao_mantem_o_original(monkeypatch):
    # Caso reproduzido na revisão: mesmos números, a alta virou queda.
    invertida = DECOMPOSICAO.texto.replace("maior", "menor").replace("a alta", "a queda")
    assert is_faithful(invertida, DECOMPOSICAO.dados)  # os números sozinhos não pegam a troca
    _patch(monkeypatch, output=invertida)
    assert rewriter.rewrite_insights([DECOMPOSICAO])[0].texto == DECOMPOSICAO.texto


@pytest.mark.parametrize("text", [
    # Direção trocada em um dos efeitos.
    "A conta de jun/2026 ficou R$ 4,07 maior que em jun/2025: o kWh mais caro somou R$ 5,94 e o consumo maior somou R$ 1,87.",
    # Unidade trocada: R$ virou %.
    "A conta de jun/2026 ficou 4,07% maior que em jun/2025, puxada pelo kWh mais caro (R$ 5,94 a mais).",
    # Número sem a unidade do original.
    "A conta de jun/2026 ficou 4,07 maior que em jun/2025.",
    # Indicador trocado: o efeito do preço atribuído ao consumo e vice-versa.
    "O valor da energia na conta de jun/2026 ficou R$ 4,07 maior que em jun/2025: a alta veio do consumo maior "
    "(R$ 5,94 a mais), compensada em parte pelo kWh mais barato (R$ 1,87 a menos).",
    # Indicador trocado: a variação da conta atribuída ao consumo.
    "O consumo de jun/2026 ficou R$ 4,07 maior que em jun/2025.",
    # Negação inverte o sentido.
    "O valor da energia na conta de jun/2026 não ficou R$ 4,07 maior que em jun/2025.",
])
def test_direcao_unidade_e_indicador_precisam_ser_preservados(text):
    assert not preserves_meaning(text, DECOMPOSICAO.texto)


def test_reescrita_equivalente_e_aceita(monkeypatch):
    texto = ("Em jun/2026, a conta ficou R$ 4,07 maior que em jun/2025, puxada pelo kWh mais caro (R$ 5,94 a mais); "
             "o consumo menor compensou parte disso (R$ 1,87 a menos).")
    _patch(monkeypatch, output=texto)
    assert rewriter.rewrite_insights([DECOMPOSICAO])[0].texto == texto


def test_reescrita_nao_pode_criar_direcao():
    original = "O consumo de jun/2026 está em linha com a média dos 6 meses anteriores (140 kWh)."
    assert not preserves_meaning("Em jun/2026, o consumo ficou acima da média dos 6 meses anteriores (140 kWh).", original)
    assert preserves_meaning("Em jun/2026, o consumo seguiu em linha com a média dos 6 meses anteriores (140 kWh).", original)
