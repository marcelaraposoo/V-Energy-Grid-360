"""Dashboard com município: cadastro/GD e classes pela A3, e o bloco de operação (atendimentos e DEC/FEC)."""
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.dashboard import router
from app.routers.deps import repo_dep
from app.schemas import Periodo
from app.services import continuidade
from app.services.dashboard_complementares import CLASSES, cadastro_gd, consumo_classes, consumo_locais, operacao
from tests.gold_fixture import criar_gold_db

ATUAL = Periodo(inicio="2026-01", fim="2026-02")
BASE = Periodo(inicio="2025-01", fim="2025-02")


def _atendimentos(*meses):
    return [dict(mes_referencia=m, qtd_atendimentos=q, qtd_avaliacoes=a, soma_notas=s) for m, q, a, s in meses]


@pytest.fixture
def repo():
    a3 = [dict(mes_referencia=mes, municipio=municipio, bairro="Centro", classe=classe, consumo_kwh=10,
               qtd_ucs_cadastradas=ucs, qtd_ucs_com_gd=gd)
          for mes in ("2025-02", "2026-02")
          for municipio, ucs, gd in (("Recife", 30, 3), ("Olinda", 10, 1))
          for classe in CLASSES]
    return SimpleNamespace(
        a3=a3,
        kpis_mensais=Mock(return_value=[]),
        segmentos_mensais=Mock(side_effect=lambda inicio, fim, municipio=None, *_: [
            r for r in a3 if inicio <= r["mes_referencia"] <= fim and municipio in (None, r["municipio"])]),
        atendimentos_mensais=Mock(side_effect=lambda inicio, fim, municipio=None: {
            ("2026-01", "2026-02"): _atendimentos(("2026-01", 10, 8, 32.0), ("2026-02", 30, 2, 10.0)),
            ("2025-01", "2025-02"): _atendimentos(("2025-02", 20, 20, 90.0)),
        }[(inicio, fim)]),
        indicadores_continuidade=Mock(side_effect=lambda inicio, fim, municipio=None, **_: [
            dict(mes_referencia=mes, alimentador=alimentador, dec_horas=dec, fec=fec, qtd_ucs_alimentador_mes=ucs,
                 qtd_interrupcoes=3, horas_interrompidas=dec * ucs)
            for mes in ("2026-01", "2026-02") if inicio <= mes <= fim
            for alimentador, dec, fec, ucs in (("ALM-A", 2.0, 1.0, 100), ("ALM-B", 0.5, 0.2, 300))]),
    )


def test_cadastro_com_municipio_soma_os_segmentos_da_a3_sem_ler_a_a5(repo):
    resultado = cadastro_gd(repo, BASE, ATUAL, "Recife")
    assert resultado.atual.qtd_ucs_cadastradas == 30 * len(CLASSES)
    assert resultado.atual.qtd_ucs_com_gd == 3 * len(CLASSES)
    assert resultado.atual.percentual_gd == 10
    assert resultado.variacao_cadastradas_pct == 0
    repo.kpis_mensais.assert_not_called()
    assert [c.args for c in repo.segmentos_mensais.call_args_list] == [("2026-02", "2026-02", "Recife"), ("2025-02", "2025-02", "Recife")]


def test_cadastro_de_municipio_sem_segmentos_fica_indisponivel(repo):
    resultado = cadastro_gd(repo, None, Periodo(inicio="2026-01", fim="2026-01"), "Recife")
    assert resultado.atual.qtd_ucs_cadastradas is resultado.atual.qtd_ucs_com_gd is None


def test_classes_com_municipio_filtram_a_a3(repo):
    resultado = consumo_classes(repo, None, Periodo(inicio="2026-02", fim="2026-02"), "Olinda")
    assert resultado.consumo_total_kwh == 10 * len(CLASSES)
    assert repo.segmentos_mensais.call_args.args[2] == "Olinda"


def test_consumo_por_municipio_soma_bairros_e_classes_e_ordena_pelo_volume(repo):
    resultado = consumo_locais(repo, Periodo(inicio="2025-02", fim="2025-02"), Periodo(inicio="2026-02", fim="2026-02"))
    assert resultado.nivel == "municipio"
    assert [(l.municipio, l.bairro) for l in resultado.locais] == [("Olinda", None), ("Recife", None)]  # empate: ordem alfabética
    assert resultado.consumo_total_kwh == 2 * 10 * len(CLASSES)
    assert [l.participacao_pct for l in resultado.locais] == [50, 50]
    assert resultado.locais[0].variacao_pct == 0


def test_consumo_com_municipio_desce_a_bairro(repo):
    repo.a3.append(dict(repo.a3[0], bairro="Boa Vista", municipio="Recife", consumo_kwh=500, mes_referencia="2026-02", classe="RURAL"))
    resultado = consumo_locais(repo, None, Periodo(inicio="2026-02", fim="2026-02"), "Recife")
    assert resultado.nivel == "bairro" and resultado.municipio == "Recife"
    assert [(l.bairro, l.consumo_kwh) for l in resultado.locais] == [("Boa Vista", 500), ("Centro", 50)]
    assert all(l.variacao_pct is None and l.consumo_referencia_kwh is None for l in resultado.locais)


def test_local_sem_um_dos_meses_fica_indisponivel_e_derruba_as_participacoes(repo):
    resultado = consumo_locais(repo, None, Periodo(inicio="2026-01", fim="2026-02"))
    assert {l.municipio: l.competencias_ausentes for l in resultado.locais} == {"Olinda": ["2026-01"], "Recife": ["2026-01"]}
    assert all(l.consumo_kwh is None and l.participacao_pct is None for l in resultado.locais)
    assert resultado.consumo_total_kwh is None


def test_operacao_soma_chamados_e_pondera_a_nota_pelas_avaliacoes(repo):
    resultado = operacao(repo, BASE, ATUAL)
    # Nota = soma das notas ÷ avaliações (42 ÷ 10), não a média das médias mensais (4,0 e 5,0).
    assert resultado.atual.qtd_atendimentos == 40
    assert resultado.atual.qtd_avaliacoes == 10
    assert resultado.atual.nota_satisfacao_media == 4.2
    assert resultado.base.qtd_atendimentos == 20  # Mês sem chamado (2025-01) conta como zero.
    assert resultado.base.nota_satisfacao_media == 4.5
    assert resultado.variacao_atendimentos_pct == 100
    assert resultado.variacao_satisfacao == -0.3


def test_operacao_usa_o_mesmo_dec_fec_da_qualidade_do_servico(repo):
    resultado = operacao(repo, None, ATUAL, "Recife")
    assert repo.indicadores_continuidade.call_args.kwargs == {"municipio": "Recife"}
    esperado = continuidade.resumo_periodo(repo.indicadores_continuidade("2026-01", "2026-02"))
    assert resultado.atual.dec_horas == round(esperado["dec_horas"], 2) == 1.75  # (2×100 + 0,5×300) ÷ 400, em 2 meses
    assert resultado.atual.fec_vezes == round(esperado["fec_vezes"], 2)
    assert resultado.atual.qtd_interrupcoes == 12
    assert resultado.base is None
    assert resultado.variacao_dec_pct is resultado.variacao_satisfacao is None
    assert repo.atendimentos_mensais.call_args.args == ("2026-01", "2026-02", "Recife")


def test_variacao_sai_dos_valores_exatos_e_nao_dos_arredondados(repo):
    # 1,006 h × 1,004 h: arredondados (1,01 × 1,00) dariam +1%; o exato é +0,2%, como na Qualidade do Serviço.
    repo.indicadores_continuidade = Mock(side_effect=lambda inicio, fim, municipio=None, **_: [dict(
        mes_referencia=inicio, alimentador="ALM-A", dec_horas=1.006 if inicio == "2026-01" else 1.004, fec=1.0,
        qtd_ucs_alimentador_mes=100, qtd_interrupcoes=1, horas_interrompidas=100)])
    resultado = operacao(repo, BASE, ATUAL)
    assert (resultado.atual.dec_horas, resultado.base.dec_horas) == (1.01, 1.0)
    assert resultado.variacao_dec_pct == 0.2


def test_operacao_sem_dados_nao_inventa_zeros(repo):
    repo.atendimentos_mensais = Mock(return_value=[])
    repo.indicadores_continuidade = Mock(return_value=[])
    resultado = operacao(repo, None, ATUAL)
    assert resultado.atual.qtd_atendimentos == 0
    assert resultado.atual.nota_satisfacao_media is None
    assert resultado.atual.dec_horas is resultado.atual.fec_vezes is resultado.atual.qtd_interrupcoes is None


def test_sqlite_equivale_ao_mock_com_e_sem_municipio(tmp_path):
    mock = MockRepository()
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        for tabela in ("kpis_mensal", "fato_segmento_mensal", "fato_atendimento", "dec_fec_alimentador_mensal"):
            colunas = list(mock.d[tabela][0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                            [[r[c] for c in colunas] for r in mock.d[tabela]])
    sqlite = SqliteRepository(path)
    atual, base = Periodo(inicio="2025-07", fim="2026-06"), Periodo(inicio="2024-07", fim="2025-06")
    def meses(repo, municipio):
        return [{**m, "soma_notas": round(m["soma_notas"], 6)} for m in repo.atendimentos_mensais("2025-07", "2026-06", municipio)]

    for municipio in (None, "Recife"):
        assert meses(sqlite, municipio) == meses(mock, municipio)
        assert operacao(sqlite, base, atual, municipio) == operacao(mock, base, atual, municipio)
        assert cadastro_gd(sqlite, base, atual, municipio) == cadastro_gd(mock, base, atual, municipio)
        assert consumo_classes(sqlite, base, atual, municipio) == consumo_classes(mock, base, atual, municipio)
        assert consumo_locais(sqlite, base, atual, municipio) == consumo_locais(mock, base, atual, municipio)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    mock = MockRepository()
    app.dependency_overrides[repo_dep] = lambda: mock
    with TestClient(app) as client:
        yield client


PERIODOS = {"atual_inicio": "2025-07", "atual_fim": "2026-06", "base_inicio": "2024-07", "base_fim": "2025-06"}


def test_endpoint_operacao_com_e_sem_municipio(client):
    geral = client.get("/api/dashboard/operacao", params=PERIODOS)
    recife = client.get("/api/dashboard/operacao", params={**PERIODOS, "municipio": "Recife"})
    assert geral.status_code == recife.status_code == 200
    assert recife.json()["municipio"] == "Recife"
    assert 0 < recife.json()["atual"]["qtd_atendimentos"] < geral.json()["atual"]["qtd_atendimentos"]
    sem_referencia = client.get("/api/dashboard/operacao", params={"comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-06"})
    assert sem_referencia.json()["base"] is None


@pytest.mark.parametrize("rota", ["operacao", "cadastro-gd", "consumo-classes", "consumo-locais"])
def test_municipio_desconhecido_e_422(client, rota):
    resposta = client.get(f"/api/dashboard/{rota}", params={**PERIODOS, "municipio": "Atlântida"})
    assert resposta.status_code == 422
    assert "Município desconhecido" in resposta.json()["detail"]


@pytest.mark.parametrize("rota", ["cadastro-gd", "consumo-classes"])
def test_blocos_complementares_aceitam_municipio(client, rota):
    geral = client.get(f"/api/dashboard/{rota}", params=PERIODOS).json()
    recife = client.get(f"/api/dashboard/{rota}", params={**PERIODOS, "municipio": "Recife"}).json()
    if rota == "cadastro-gd":
        assert 0 < recife["atual"]["qtd_ucs_cadastradas"] < geral["atual"]["qtd_ucs_cadastradas"]
    else:
        assert 0 < recife["consumo_total_kwh"] < geral["consumo_total_kwh"]


def test_endpoint_consumo_locais_bate_com_o_total_das_classes(client):
    for municipio in (None, "Recife"):
        params = {**PERIODOS, **({"municipio": municipio} if municipio else {})}
        locais = client.get("/api/dashboard/consumo-locais", params=params).json()
        classes = client.get("/api/dashboard/consumo-classes", params=params).json()
        assert locais["nivel"] == ("bairro" if municipio else "municipio")
        assert locais["consumo_total_kwh"] == pytest.approx(classes["consumo_total_kwh"])
        volumes = [l["consumo_kwh"] for l in locais["locais"]]
        assert volumes == sorted(volumes, reverse=True)
