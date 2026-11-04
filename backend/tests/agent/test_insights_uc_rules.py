"""Insights da Visão 360: interpretam a conta (consumo × preço) e o padrão do consumo."""
from types import SimpleNamespace

import pytest

from app.agent.insights.uc_rules import insights_uc


def _visao(atual="2026-06", ref="2025-06", troca_atual=False, troca_ref=False, interrupcoes=(0, 0)):
    return SimpleNamespace(
        diagnostico_conta_alta=SimpleNamespace(
            competencia_atual=atual, competencia_referencia=ref,
            troca_medidor_atual=troca_atual, troca_medidor_referencia=troca_ref,
        ),
        interrupcoes=SimpleNamespace(qtd_ocorrencias=interrupcoes[0], duracao_total_min=interrupcoes[1],
                                     periodo_inicio="2025-07", periodo_fim="2026-06"),
    )


def _fatura(competencia, consumo, preco, bandeira="Verde"):
    return {"competencia": competencia, "consumo_kwh": consumo, "valor_energia": round(consumo * preco, 2), "bandeira": bandeira}


def _historico(consumo_atual=77, preco_atual=0.605, bandeira_atual="Amarela", seis=(140, 150, 160, 150, 140, 100),
               seis_ano_anterior=(130, 140, 150, 140, 130, 100), consumo_ref=81, preco_ref=0.6238):
    """jun/2026 (analisado) e os 6 meses antes; jun/2025 (referência) e os 6 meses antes dele."""
    meses = ["12", "01", "02", "03", "04", "05"]
    atual = [_fatura(f"{2025 if m == '12' else 2026}-{m}", c, 0.6) for m, c in zip(meses, seis)]
    anterior = [_fatura(f"{2024 if m == '12' else 2025}-{m}", c, 0.6) for m, c in zip(meses, seis_ano_anterior)]
    return [*anterior, _fatura("2025-06", consumo_ref, preco_ref, "Vermelha P1"), *atual,
            _fatura("2026-06", consumo_atual, preco_atual, bandeira_atual)]


def _textos(faturas, **visao):
    return [i.texto for i in insights_uc(_visao(**visao), faturas)]


def test_decomposicao_separa_consumo_e_preco_e_cita_a_bandeira():
    insight = insights_uc(_visao(), _historico())[0]
    assert insight.texto == ("O valor da energia na conta de jun/2026 ficou R$ 3,94 menor que em jun/2025: a queda veio do "
                             "consumo menor (R$ 2,50 a menos) e do kWh mais barato (R$ 1,44 a menos), "
                             "com bandeira amarela em jun/2026, contra vermelha P1 em jun/2025.")
    assert insight.tipo == "informativo"
    # Os dois efeitos fecham a variação.
    assert insight.dados["efeito_consumo"] + insight.dados["efeito_preco"] == pytest.approx(insight.dados["variacao_energia"], abs=0.01)


def test_conta_que_sobe_pelo_preco_e_destaque():
    insight = insights_uc(_visao(), _historico(consumo_atual=78, preco_atual=0.70))[0]
    assert insight.texto.startswith("O valor da energia na conta de jun/2026 ficou R$ 4,07 maior que em jun/2025: a alta veio do "
                                    "kWh mais caro (R$ 5,94 a mais), compensada em parte pelo consumo menor (R$ 1,87 a menos)")
    assert insight.tipo == "destaque"


def test_efeito_de_centavos_nao_e_citado():
    # Consumo explica R$ 28,70 da alta; o preço, R$ 0,15 (menos de 5% do maior efeito).
    insight = insights_uc(_visao(), _historico(consumo_atual=127, preco_atual=0.625))[0]
    assert insight.texto == ("O valor da energia na conta de jun/2026 ficou R$ 28,85 maior que em jun/2025: "
                             "a alta veio quase toda do consumo maior.")
    # Sem o efeito do preço no texto, a bandeira (que explica o preço) também sai; o valor continua nos dados.
    assert insight.dados["efeito_preco"] == pytest.approx(0.15, abs=0.01)


def test_variacao_de_um_efeito_so_nao_repete_o_valor():
    faturas = _historico(consumo_atual=81, preco_atual=0.70)
    faturas[6] = _fatura("2025-06", 81, 0.6238, "Amarela")
    assert insights_uc(_visao(), faturas)[0].texto == (
        "O valor da energia na conta de jun/2026 ficou R$ 6,17 maior que em jun/2025: a alta veio toda do kWh mais caro.")


def test_consumo_semelhante_ao_ano_anterior_e_fora_do_padrao():
    semelhante = _textos(_historico())[1]
    assert semelhante == ("O consumo de jun/2026 ficou 45,0% abaixo da média dos 6 meses anteriores (140 kWh), "
                          "comportamento semelhante ao observado no ano anterior (em jun/2025, ficou 38,5% abaixo).")
    # A comparação com o ano anterior, sozinha, não comprova sazonalidade.
    assert "sazonal" not in semelhante
    fora = insights_uc(_visao(), _historico(consumo_atual=200))[1]
    assert fora.texto == ("O consumo de jun/2026 ficou 42,9% acima da média dos 6 meses anteriores (140 kWh), "
                          "fora do padrão do ano anterior (em jun/2025, ficou 38,5% abaixo).")
    assert fora.tipo == "alerta"


def test_consumo_em_linha_e_sem_historico_suficiente():
    assert _textos(_historico(consumo_atual=135))[1] == "O consumo de jun/2026 está em linha com a média dos 6 meses anteriores (140 kWh)."
    poucas = [_fatura("2025-06", 81, 0.62), _fatura("2026-05", 100, 0.6), _fatura("2026-06", 77, 0.6)]
    assert not any(t.startswith("O consumo de") for t in _textos(poucas))


def test_historico_parcial_informa_quantos_meses_entraram_na_media():
    # Sem fatura em jan e mar/2026: a média usa 4 dos 6 meses (140, 160, 140, 100 → 135 kWh).
    faturas = [f for f in _historico() if f["competencia"] not in ("2026-01", "2026-03")]
    insight = insights_uc(_visao(ref="2026-05"), faturas)[1]
    assert insight.texto == "O consumo de jun/2026 ficou 43,0% abaixo da média dos 4 meses com fatura entre os 6 anteriores (135 kWh)."
    assert insight.dados["meses_na_media"] == 4 and insight.dados["janela_media_meses"] == 6
    em_linha = [*faturas[:-1], _fatura("2026-06", 130, 0.6)]
    assert _textos(em_linha, ref="2026-05")[1] == "O consumo de jun/2026 está em linha com a média dos 4 meses com fatura entre os 6 anteriores (135 kWh)."


def test_historico_parcial_no_ano_anterior_tambem_e_informado():
    # Sem fatura em jan, fev e mar/2025: a média de jun/2025 usa 3 dos 6 meses (130, 130, 100 → 120 kWh).
    faturas = [f for f in _historico() if f["competencia"] not in ("2025-01", "2025-02", "2025-03")]
    insight = insights_uc(_visao(), faturas)[1]
    assert insight.texto == ("O consumo de jun/2026 ficou 45,0% abaixo da média dos 6 meses anteriores (140 kWh), "
                             "comportamento semelhante ao observado no ano anterior (em jun/2025, ficou 32,5% abaixo "
                             "da média dos 3 meses com fatura entre os 6 anteriores).")
    assert insight.dados["meses_na_media_referencia"] == 3


def test_sem_mesmo_mes_do_ano_anterior_nao_compara_com_o_ano_anterior():
    textos = _textos(_historico(), ref="2026-05")
    assert textos[1] == "O consumo de jun/2026 ficou 45,0% abaixo da média dos 6 meses anteriores (140 kWh)."


def test_troca_de_medidor_e_interrupcoes_em_horas():
    textos = _textos([], troca_atual=True, troca_ref=True, interrupcoes=(26, 4159))
    assert textos == [
        "Houve troca de medidor em jun/2025 e jun/2026: no mês da troca, o consumo usa a leitura do medidor novo.",
        "Entre jul/2025 e jun/2026, a UC teve 26 interrupções, somando 69,3 horas sem energia.",
    ]
    assert _textos([], interrupcoes=(1, 90))[-1].endswith("a UC teve 1 interrupção, somando 1,5 horas sem energia.")


def test_textos_nao_usam_hifen_como_sinal_e_dados_trazem_os_meses():
    insights = insights_uc(_visao(interrupcoes=(2, 270)), _historico())
    assert not any(" -" in i.texto for i in insights)
    assert insights[0].dados["mes_atual"] == "jun/2026" and insights[0].dados["ano_referencia"] == 2025
