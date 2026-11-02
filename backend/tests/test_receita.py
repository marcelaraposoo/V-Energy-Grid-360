"""Análise de Receita: decomposição pela A3, UCs do último mês, GD nas mesmas UCs pela A2 e série."""
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoDisponivelNaGold
from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.schemas import Filtros, Periodo
from app.services import receita
from app.services.receita import PERIODOS_DIAGNOSTICO
from tests.gold_fixture import criar_gold_db

BASE = Periodo(inicio="2025-01", fim="2025-02")
ATUAL = Periodo(inicio="2026-01", fim="2026-02")


def _seg(mes, bairro, classe="RESIDENCIAL", kwh=0, receita_=0, ucs=0, gd=0, faturas=0, nao_verde=0, trocas=0, municipio="Recife"):
    return {
        "mes_referencia": mes, "municipio": municipio, "bairro": bairro, "classe": classe,
        "consumo_kwh": kwh, "receita_energia": receita_, "qtd_ucs_faturadas": ucs, "qtd_ucs_com_gd": gd,
        "qtd_faturas": faturas, "qtd_faturas_bandeira_nao_verde": nao_verde, "qtd_trocas_medidor": trocas,
    }


SEGMENTOS = [
    _seg("2025-01", "Centro", kwh=1000, receita_=500, ucs=10, faturas=10),
    _seg("2025-02", "Centro", kwh=1000, receita_=500, ucs=11, faturas=11),
    _seg("2025-01", "Centro", municipio="Olinda", kwh=400, receita_=200, ucs=4, faturas=4),
    _seg("2025-02", "Centro", municipio="Olinda", kwh=400, receita_=200, ucs=4, faturas=4),
    _seg("2026-01", "Centro", kwh=900, receita_=540, ucs=12, gd=1, faturas=12, nao_verde=6, trocas=2),
    _seg("2026-02", "Centro", kwh=800, receita_=480, ucs=12, gd=2, faturas=12, nao_verde=12, trocas=1),
    _seg("2026-01", "Centro", municipio="Olinda", kwh=400, receita_=240, ucs=4, faturas=4),
    _seg("2026-02", "Centro", municipio="Olinda", kwh=400, receita_=240, ucs=4, faturas=4),
    # Segmento novo: sem volume na referência (regra de volume zero da A4).
    _seg("2026-02", "Centro", classe="COMERCIAL", kwh=100, receita_=70, ucs=1, faturas=1),
]


def _repo(segmentos=SEGMENTOS, gd=None):
    def segmentos_mensais(inicio, fim, municipio=None, bairro=None, classe=None):
        return [s for s in segmentos if inicio <= s["mes_referencia"] <= fim
                and municipio in (None, s["municipio"]) and bairro in (None, s["bairro"]) and classe in (None, s["classe"])]
    return SimpleNamespace(
        segmentos_mensais=segmentos_mensais, gd_mesmas_ucs=Mock(return_value=gd),
        classes=lambda: {"RESIDENCIAL": "Residencial", "COMERCIAL": "Comercial"},
    )


@pytest.mark.parametrize("agrupar_por", ["municipio", "bairro", "classe"])
def test_efeitos_fecham_e_linhas_somam_o_total(agrupar_por):
    v = receita.variacao(_repo(), BASE, ATUAL, Filtros(), agrupar_por)
    for linha in [v.total, *v.linhas]:
        assert linha.efeito_volume + linha.efeito_preco == pytest.approx(linha.variacao_receita, abs=0.02)
    for campo in ("receita_base", "receita_atual", "energia_base_kwh", "energia_atual_kwh", "qtd_ucs_base", "qtd_ucs_atual"):
        assert sum(getattr(l, campo) for l in v.linhas) == pytest.approx(getattr(v.total, campo))
    assert [l.variacao_receita for l in v.linhas] == sorted(l.variacao_receita for l in v.linhas)


def test_valores_da_decomposicao_e_ucs_da_ultima_competencia():
    t = receita.variacao(_repo(), BASE, ATUAL, Filtros(), "municipio").total
    assert (t.energia_base_kwh, t.energia_atual_kwh, t.receita_base, t.receita_atual) == (2800, 2600, 1400, 1570)
    assert t.preco_base_kwh == pytest.approx(0.5)
    assert t.efeito_volume == pytest.approx((2600 - 2800) * 0.5)
    # Último mês de cada período, sem somar meses (somar contaria a mesma UC duas vezes).
    assert (t.qtd_ucs_base, t.qtd_ucs_atual) == (15, 17)


def test_segmento_sem_volume_na_referencia_atribui_tudo_ao_volume():
    v = receita.variacao(_repo(), BASE, ATUAL, Filtros(), "classe")
    comercial = next(l for l in v.linhas if l.classe == "COMERCIAL")
    assert comercial.rotulo == "Comercial"
    assert comercial.preco_base_kwh is None and comercial.preco_atual_kwh == pytest.approx(0.7)
    assert (comercial.efeito_volume, comercial.efeito_preco) == (70, 0)
    assert comercial.variacao_receita_pct is None and comercial.variacao_energia_pct is None


def test_bairro_homonimo_fica_separado_por_municipio():
    v = receita.variacao(_repo(), BASE, ATUAL, Filtros(classe="RESIDENCIAL"), "bairro")
    assert {(l.chave, l.rotulo, l.municipio) for l in v.linhas} == {
        ("Centro - Recife", "Centro", "Recife"), ("Centro - Olinda", "Centro", "Olinda"),
    }


def test_gd_vem_da_a2_em_qualquer_recorte_com_os_filtros():
    repo = _repo(gd={"qtd_ucs": 3, "energia_base_kwh": 350.04, "energia_atual_kwh": 120.0})
    v = receita.variacao(repo, BASE, ATUAL, Filtros(municipio="Recife", classe="RESIDENCIAL"), "bairro")
    assert v.recorte == "personalizado"
    repo.gd_mesmas_ucs.assert_called_once_with("2025-01", "2025-02", "2026-01", "2026-02", "Recife", None, "RESIDENCIAL")
    f = v.fatores
    assert (f.qtd_ucs_com_gd, f.energia_ucs_gd_base_kwh, f.energia_ucs_gd_atual_kwh) == (3, 350.0, 120.0)
    base, atual = PERIODOS_DIAGNOSTICO
    assert receita.variacao(repo, base, atual, Filtros(), "municipio").recorte == "diagnostico"


def test_sem_a2_os_volumes_de_gd_ficam_nulos_e_a_contagem_vem_da_a3():
    v = receita.variacao(_repo(gd=None), BASE, ATUAL, Filtros(), "municipio")
    f = v.fatores
    assert f.energia_ucs_gd_base_kwh is f.energia_ucs_gd_atual_kwh is None
    assert (f.qtd_ucs_com_gd, f.qtd_trocas_medidor_atual) == (2, 3)
    assert f.pct_faturas_bandeira_nao_verde_base == 0
    assert f.pct_faturas_bandeira_nao_verde_atual == pytest.approx(18 / 33 * 100, abs=0.01)


def test_serie_traz_referencia_e_atual_sem_inventar_meses_ausentes():
    segmentos = [s for s in SEGMENTOS if s["mes_referencia"] != "2025-02"]
    serie = receita.variacao(_repo(segmentos), BASE, ATUAL, Filtros(), "municipio").serie
    assert [p.competencia for p in serie] == ["2025-01", "2025-02", "2026-01", "2026-02"]
    assert serie[1].receita is serie[1].energia_kwh is serie[1].tarifa_media is None
    assert (serie[3].energia_kwh, serie[3].receita) == (1300, 790)


client = TestClient(app)


def test_api_mock_padrao_e_o_recorte_do_diagnostico_com_gd():
    v = client.get("/api/receita/variacao").json()
    assert v["recorte"] == "diagnostico"
    assert v["fatores"]["energia_ucs_gd_base_kwh"] is not None
    assert len(v["serie"]) == 24
    assert {"rotulo", "preco_base_kwh", "qtd_ucs_atual"} <= set(v["total"])


def test_api_periodos_personalizados_tambem_trazem_gd_e_invalidos_sao_recusados():
    ok = client.get("/api/receita/variacao?base_inicio=2025-01&base_fim=2025-06&atual_inicio=2026-01&atual_fim=2026-06")
    assert ok.status_code == 200 and ok.json()["recorte"] == "personalizado"
    assert ok.json()["fatores"]["energia_ucs_gd_atual_kwh"] is not None
    sobrepostos = client.get("/api/receita/variacao?base_inicio=2025-01&base_fim=2025-06&atual_inicio=2025-06&atual_fim=2025-11")
    assert sobrepostos.status_code == 422


def _fatura(uc, mes, kwh, gd, municipio="RECIFE", classe="RESIDENCIAL"):
    return (uc, mes, gd, kwh, municipio, "CENTRO", classe)


@pytest.fixture
def gold_a2(tmp_path):
    caminho = criar_gold_db(tmp_path / "gold.db")
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE fato_consumo_faturamento (id_uc TEXT, mes_referencia TEXT, possui_gd_no_mes,"
                " consumo_kwh INTEGER, municipio TEXT, bairro TEXT, classe TEXT)")
    con.executemany("INSERT INTO fato_consumo_faturamento VALUES (?, ?, ?, ?, ?, ?, ?)", [
        # UC1: GD conectada no período atual. Entra nos DOIS períodos (mesmas UCs).
        _fatura("UC1", "2025-01", 300, 0), _fatura("UC1", "2026-01", 100, 0), _fatura("UC1", "2026-02", 50, 1),
        # UC2: booleano em texto, como pode vir da exportação.
        _fatura("UC2", "2025-02", 200, "false"), _fatura("UC2", "2026-02", 80, "true"),
        # UC3: conecta só depois do fim do período atual. Não entra.
        _fatura("UC3", "2025-01", 999, 0), _fatura("UC3", "2026-02", 999, 0), _fatura("UC3", "2026-03", 10, 1),
        # UC4: outro município. Sai com o filtro.
        _fatura("UC4", "2025-01", 40, 0, municipio="OLINDA"), _fatura("UC4", "2026-02", 20, 1.0, municipio="OLINDA"),
    ])
    con.commit()
    con.close()
    return caminho


def test_sqlite_gd_nas_mesmas_ucs_e_filtros(gold_a2):
    repo = SqliteRepository(gold_a2)
    assert repo.gd_mesmas_ucs("2025-01", "2025-02", "2026-01", "2026-02") == {
        "qtd_ucs": 3, "energia_base_kwh": 540.0, "energia_atual_kwh": 250.0,
    }
    assert repo.gd_mesmas_ucs("2025-01", "2025-02", "2026-01", "2026-02", municipio="RECIFE") == {
        "qtd_ucs": 2, "energia_base_kwh": 500.0, "energia_atual_kwh": 230.0,
    }


def test_sqlite_a2_ausente_devolve_nulo_e_incompleta_avisa(tmp_path, gold_a2):
    assert SqliteRepository(criar_gold_db(tmp_path / "sem_a2.db")).gd_mesmas_ucs("2025-01", "2025-02", "2026-01", "2026-02") is None
    con = sqlite3.connect(gold_a2)
    con.execute("ALTER TABLE fato_consumo_faturamento DROP COLUMN possui_gd_no_mes")
    con.commit()
    con.close()
    with pytest.raises(NaoDisponivelNaGold, match="possui_gd_no_mes"):
        SqliteRepository(gold_a2).gd_mesmas_ucs("2025-01", "2025-02", "2026-01", "2026-02")


def test_mock_contagem_de_gd_da_a2_bate_com_a_a3_no_ultimo_mes():
    repo = MockRepository()
    for atual in ("2026-06", "2025-12"):
        a3 = sum(r["qtd_ucs_com_gd"] for r in repo.segmentos_mensais(atual, atual))
        assert repo.gd_mesmas_ucs("2022-07", "2022-12", "2025-07", atual)["qtd_ucs"] == a3
