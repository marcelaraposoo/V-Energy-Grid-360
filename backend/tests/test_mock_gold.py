import re
from datetime import date
from decimal import Decimal

import pytest

from app.mock.mock_data import DATA_REFERENCIA, build_mock_data
from app.repositories.mock_repo import MockRepository
from app.services.unidades import visao_360


@pytest.fixture(scope="module")
def dados():
    return build_mock_data()


def test_dim_uc_segue_contrato_gold(dados):
    campos = set("""
        id_uc nome_titular_mascarado documento_mascarado tipo_pessoa logradouro numero
        bairro municipio uf cep latitude longitude classe subgrupo_tarifario alimentador
        data_ligacao data_ligacao_estimada status id_medidor_ativo tipo_medidor_ativo
        modelo_medidor_ativo data_instalacao_medidor idade_medidor_anos
        medidor_trocado_recentemente possui_gd potencia_gd_kwp data_conexao_gd modalidade_gd
        energia_injetada_media_kwh energia_injetada_atipica primeiro_mes_leitura ultimo_mes_leitura
        consumo_medio_12m_kwh consumo_medio_12m_anterior_kwh variacao_consumo_12m_pct
    """.split())
    classes = {"RESIDENCIAL": "B1", "RURAL": "B2", "COMERCIAL": "B3", "PODER PUBLICO": "B3", "INDUSTRIAL": "A4"}
    assert len(dados["dim_uc"]) == 400
    assert len({uc["id_uc"] for uc in dados["dim_uc"]}) == 400
    for uc in dados["dim_uc"]:
        assert set(uc) == campos
        assert re.fullmatch(r"UC\d{6}", uc["id_uc"])
        assert re.fullmatch(r"\S+(?: [A-ZÁÉÍÓÚÂÊÔÃÕÇ]\*\*\*)+", uc["nome_titular_mascarado"])
        assert "*" in uc["documento_mascarado"]
        assert uc["logradouro"] and uc["numero"]
        assert uc["subgrupo_tarifario"] == classes[uc["classe"]]
        assert uc["status"] == "ATIVA"
        assert uc["uf"] == "PE"
        assert uc["primeiro_mes_leitura"] == "2022-07"
        assert uc["ultimo_mes_leitura"] == "2026-06"
        assert uc["tipo_medidor_ativo"] in ("ELETRONICO", "ELETROMECANICO", "SMART")
        assert uc["data_ligacao"] <= uc["data_instalacao_medidor"] <= "2022-07-01"
        assert uc["idade_medidor_anos"] >= 0
        assert isinstance(uc["possui_gd"], bool)
        if uc["possui_gd"]:
            assert date.fromisoformat(uc["data_conexao_gd"]) <= DATA_REFERENCIA
            assert uc["potencia_gd_kwp"] > 0
        else:
            assert uc["data_conexao_gd"] is None
            assert uc["potencia_gd_kwp"] is None


def test_fato_consumo_faturamento_segue_contrato_gold(dados):
    campos = set("""
        id_uc mes_referencia ano mes periodo_diagnostico classe bairro municipio possui_gd_no_mes
        id_medidor data_leitura tipo_leitura consumo_kwh consumo_kwh_ano_anterior
        variacao_consumo_ano_anterior_pct troca_medidor consumo_corrigido leitura_anterior_ausente
        id_fatura data_emissao data_vencimento data_pagamento valor_energia tributos valor_total
        bandeira_tarifaria status_fatura em_aberto dias_atraso faixa_atraso preco_medio_kwh
    """.split())
    por_uc = {uc["id_uc"]: uc for uc in dados["dim_uc"]}
    fatos = dados["fato_consumo_faturamento"]
    assert len(fatos) == 400 * 48
    assert len({(f["id_uc"], f["mes_referencia"]) for f in fatos}) == len(fatos)
    assert len({f["id_fatura"] for f in fatos}) == len(fatos)
    assert dados["competencias"][0] == "2022-07"
    assert dados["competencias"][-1] == "2026-06"
    assert {f["status_fatura"] for f in fatos} == {"PAGA", "EM ABERTO"}
    assert {f["faixa_atraso"] for f in fatos} == {"EM DIA", "ATE 30 DIAS", "31 A 90 DIAS", "MAIS DE 90 DIAS"}
    for f in fatos:
        assert set(f) == campos
        uc = por_uc[f["id_uc"]]
        assert (f["classe"], f["municipio"], f["bairro"]) == (uc["classe"], uc["municipio"], uc["bairro"])
        assert f["id_medidor"] == uc["id_medidor_ativo"]
        assert type(f["consumo_kwh"]) is int
        assert f["mes_referencia"] == f"{f['ano']}-{f['mes']:02d}"
        assert Decimal(str(f["valor_total"])) == Decimal(str(f["valor_energia"])) + Decimal(str(f["tributos"]))
        assert f["bandeira_tarifaria"] in ("Verde", "Amarela", "Vermelha P1", "Vermelha P2")
        assert f["possui_gd_no_mes"] == (uc["possui_gd"] and f["mes_referencia"] >= uc["data_conexao_gd"][:7])
        pagamento = date.fromisoformat(f["data_pagamento"]) if f["data_pagamento"] else None
        vencimento = date.fromisoformat(f["data_vencimento"])
        assert f["em_aberto"] == (pagamento is None)
        assert f["status_fatura"] == ("PAGA" if pagamento else "EM ABERTO")
        assert f["dias_atraso"] == max(0, ((pagamento or DATA_REFERENCIA) - vencimento).days)
        if pagamento:
            assert date.fromisoformat(f["data_emissao"]) <= pagamento <= DATA_REFERENCIA
        esperado = "PRIMEIRO_ANO" if f["mes_referencia"] <= "2023-06" else "ULTIMOS_12M" if f["mes_referencia"] >= "2025-07" else "OUTRO"
        assert f["periodo_diagnostico"] == esperado


def test_comparacoes_e_medias_usam_a_mesma_uc_e_competencia(dados):
    por_uc = {}
    for f in dados["fato_consumo_faturamento"]:
        por_uc.setdefault(f["id_uc"], {})[f["mes_referencia"]] = f
    for uc in dados["dim_uc"]:
        fatos = por_uc[uc["id_uc"]]
        atual = sum(f["consumo_kwh"] for c, f in fatos.items() if "2025-07" <= c <= "2026-06") / 12
        anterior = sum(f["consumo_kwh"] for c, f in fatos.items() if "2024-07" <= c <= "2025-06") / 12
        assert uc["consumo_medio_12m_kwh"] == round(atual, 2)
        assert uc["consumo_medio_12m_anterior_kwh"] == round(anterior, 2)
        assert uc["variacao_consumo_12m_pct"] == round((atual / anterior - 1) * 100, 2)
        for comp, f in fatos.items():
            ano, mes = comp.split("-")
            anterior = fatos.get(f"{int(ano) - 1}-{mes}")
            assert f["consumo_kwh_ano_anterior"] == (anterior["consumo_kwh"] if anterior else None)
            if anterior:
                assert f["variacao_consumo_ano_anterior_pct"] == round((f["consumo_kwh"] / anterior["consumo_kwh"] - 1) * 100, 2)
            else:
                assert f["variacao_consumo_ano_anterior_pct"] is None


@pytest.mark.parametrize("modo", ["mes_anterior", "ano_anterior", "trimestre_ano_anterior"])
def test_mock_preenche_diagnostico_de_consumo_e_faturamento(modo):
    diagnostico = visao_360(MockRepository(), "UC000001", modo).diagnostico_conta_alta

    assert diagnostico.competencias_atuais[-1] == "2026-06"
    for metrica in (diagnostico.consumo, diagnostico.faturamento):
        assert metrica.valor_atual > 0
        assert metrica.valor_referencia > 0
        assert metrica.variacao_pct == pytest.approx((metrica.valor_atual / metrica.valor_referencia - 1) * 100)
        assert metrica.classificacao is not None


def test_filtros_e_alias_de_receita_sao_preservados():
    repo = MockRepository()
    for classe in ("B1", "B2", "B3", "A4"):
        faturas = repo.faturas("2025-07", "2026-06", classe=classe)
        assert faturas
        assert all(f["classe"] == classe for f in faturas)
        assert all(f["valor"] == f["valor_energia"] < f["valor_total"] for f in faturas)
    for uc in repo.buscar_ucs(None, None, None, 100):
        assert uc["titular"] == repo.uc(uc["uc_id"])["titular"]
        assert "***" in uc["titular"]
