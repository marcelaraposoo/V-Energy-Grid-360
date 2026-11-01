"""Posição cadastral A5 e consumo consolidado A3, sem alterar KPIs existentes."""
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
from app.schemas import Filtros, Periodo
from app.services import dashboard
from app.services.dashboard_complementares import CLASSES, cadastro_gd, consumo_classes
from tests.gold_fixture import criar_gold_db

ATUAL = Periodo(inicio="2026-01", fim="2026-02")
BASE = Periodo(inicio="2025-01", fim="2025-02")


@pytest.fixture
def repo():
    a5 = [dict(mes_referencia=mes, qtd_ucs_cadastradas=cadastradas, qtd_ucs_com_gd=gd)
          for mes, cadastradas, gd in [("2025-01", 80, 4), ("2025-02", 100, 10), ("2026-01", 200, 40), ("2026-02", 120, 18)]]
    a3 = [dict(mes_referencia=mes, municipio="Recife", bairro="Centro", classe=classe, consumo_kwh=volume)
          for mes in ("2025-01", "2025-02", "2026-01", "2026-02")
          for classe, volume in zip(CLASSES, (100, 80, 200, 20, 50))]
    return SimpleNamespace(
        a5=a5, a3=a3,
        competencias=lambda: [f"{ano}-{mes:02d}" for ano in range(2022, 2027) for mes in range(1, 13)
                             if "2022-07" <= f"{ano}-{mes:02d}" <= "2026-06"],
        kpis_mensais=Mock(side_effect=lambda inicio, fim: [r for r in a5 if inicio <= r["mes_referencia"] <= fim]),
        segmentos_mensais=Mock(side_effect=lambda inicio, fim, *_: [r for r in a3 if inicio <= r["mes_referencia"] <= fim]),
    )


def test_cadastro_consulta_somente_competencia_final_e_compara_posicoes(repo):
    resultado = cadastro_gd(repo, BASE, ATUAL)
    assert resultado.atual.qtd_ucs_cadastradas == 120
    assert resultado.atual.qtd_ucs_com_gd == 18
    assert resultado.atual.percentual_gd == 15
    assert resultado.referencia.qtd_ucs_cadastradas == 100
    assert resultado.variacao_cadastradas_pct == 20
    assert [c.args for c in repo.kpis_mensais.call_args_list] == [("2026-02", "2026-02"), ("2025-02", "2025-02")]
    repo.segmentos_mensais.assert_not_called()


def test_cadastro_sem_referencia_nao_consulta_outros_meses(repo):
    resultado = cadastro_gd(repo, None, ATUAL)
    assert resultado.referencia is resultado.variacao_cadastradas_pct is None
    repo.kpis_mensais.assert_called_once_with("2026-02", "2026-02")


def test_base_cadastral_zero_nao_produz_variacao_relativa(repo):
    repo.a5[1].update(qtd_ucs_cadastradas=0, qtd_ucs_com_gd=0)
    resultado = cadastro_gd(repo, BASE, ATUAL)
    assert resultado.atual.qtd_ucs_cadastradas == 120
    assert resultado.referencia.qtd_ucs_cadastradas == 0
    assert resultado.variacao_cadastradas_pct is None


def test_cadastro_final_ausente_nao_regride_para_mes_anterior(repo):
    repo.a5[:] = [r for r in repo.a5 if r["mes_referencia"] != "2026-02"]
    resultado = cadastro_gd(repo, BASE, ATUAL)
    assert resultado.atual.competencia == "2026-02"
    assert resultado.atual.qtd_ucs_cadastradas is resultado.atual.qtd_ucs_com_gd is resultado.atual.percentual_gd is None
    assert resultado.variacao_cadastradas_pct is None


@pytest.mark.parametrize(("quantidade", "gd", "esperado"), [(0, 0, None), (100, 0, 0), (None, 2, None), (100, None, None)])
def test_denominador_zero_e_dados_ausentes_preservam_contagens_legitimas(repo, quantidade, gd, esperado):
    repo.a5[-1].update(qtd_ucs_cadastradas=quantidade, qtd_ucs_com_gd=gd)
    resultado = cadastro_gd(repo, None, ATUAL)
    assert resultado.atual.qtd_ucs_cadastradas == quantidade
    assert resultado.atual.qtd_ucs_com_gd == gd
    assert resultado.atual.percentual_gd == esperado


@pytest.mark.parametrize("invalido", [-1, 1.5, float("nan"), float("inf")])
def test_contagem_invalida_nao_produz_percentual(repo, invalido):
    repo.a5[-1]["qtd_ucs_cadastradas"] = invalido
    assert cadastro_gd(repo, None, ATUAL).atual.percentual_gd is None


def test_posicao_a5_duplicada_e_reportada(repo):
    repo.a5.append(dict(repo.a5[-1]))
    with pytest.raises(ValueError, match="mais de uma linha"):
        cadastro_gd(repo, None, ATUAL)


def test_cinco_classes_somam_meses_e_segmentos_e_ordenam_volume_principal(repo):
    repo.a3.append(dict(mes_referencia="2026-01", municipio="Olinda", bairro="Centro", classe="RESIDENCIAL", consumo_kwh=100))
    resposta = consumo_classes(repo, BASE, ATUAL)
    assert [c.classe for c in resposta.classes] == ["INDUSTRIAL", "RESIDENCIAL", "COMERCIAL", "RURAL", "PODER PUBLICO"]
    assert resposta.consumo_total_kwh == 1000
    residencial = next(c for c in resposta.classes if c.classe == "RESIDENCIAL")
    assert residencial.consumo_kwh == 300 and residencial.participacao_pct == 30
    assert residencial.consumo_referencia_kwh == 200 and residencial.variacao_pct == 50
    assert repo.segmentos_mensais.call_count == 2
    repo.kpis_mensais.assert_not_called()


def test_consumo_ausente_por_classe_invalida_seu_acumulado_e_todas_as_participacoes(repo):
    repo.a3[:] = [r for r in repo.a3 if not (r["mes_referencia"] == "2026-01" and r["classe"] == "RURAL")]
    resposta = consumo_classes(repo, BASE, ATUAL)
    rural = next(c for c in resposta.classes if c.classe == "RURAL")
    assert rural.consumo_kwh is rural.variacao_pct is None
    assert rural.competencias_ausentes == ["2026-01"]
    assert resposta.consumo_total_kwh is None
    assert all(c.participacao_pct is None for c in resposta.classes)
    assert next(c for c in resposta.classes if c.classe == "INDUSTRIAL").consumo_kwh == 400
    assert resposta.classes[-1].classe == "RURAL"


def test_ausencia_na_referencia_nao_invalida_volume_atual_ou_participacao(repo):
    repo.a3[:] = [r for r in repo.a3 if not (r["mes_referencia"] == "2025-01" and r["classe"] == "RURAL")]
    rural = next(c for c in consumo_classes(repo, BASE, ATUAL).classes if c.classe == "RURAL")
    assert rural.consumo_kwh == 100 and rural.participacao_pct is not None
    assert rural.consumo_referencia_kwh is rural.variacao_pct is None


def test_zeros_presentes_nao_sao_lacunas_e_referencia_zero_nao_gera_variacao(repo):
    for linha in repo.a3:
        linha["consumo_kwh"] = 0
    resposta = consumo_classes(repo, BASE, ATUAL)
    assert resposta.consumo_total_kwh == 0
    for classe in resposta.classes:
        assert classe.consumo_kwh == classe.consumo_referencia_kwh == 0
        assert classe.participacao_pct is classe.variacao_pct is None
        assert classe.competencias_ausentes == []


@pytest.mark.parametrize("valor", [None, -1, float("nan"), float("inf")])
def test_consumo_nulo_ou_invalido_nao_produz_total_parcial(repo, valor):
    repo.a3[-1]["consumo_kwh"] = valor
    resposta = consumo_classes(repo, None, ATUAL)
    assert resposta.consumo_total_kwh is None
    assert next(c for c in resposta.classes if c.classe == "RURAL").consumo_kwh is None


def test_sem_comparacao_consulta_somente_principal_sem_variacoes(repo):
    resposta = consumo_classes(repo, None, ATUAL)
    repo.segmentos_mensais.assert_called_once_with("2026-01", "2026-02", None, None, None)
    assert resposta.periodo_base is None
    assert all(c.variacao_pct is c.consumo_referencia_kwh is c.competencias_ausentes_referencia is None for c in resposta.classes)


def test_segmento_duplicado_e_reportado_em_vez_de_inflar_barras(repo):
    repo.a3.append(dict(repo.a3[-1]))
    with pytest.raises(ValueError, match="segmento duplicado"):
        consumo_classes(repo, None, ATUAL)


def test_sqlite_equivale_ao_mock_e_visao_executiva_preserva_ucs_faturadas(tmp_path):
    mock = MockRepository()
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        for tabela in ("kpis_mensal", "fato_segmento_mensal"):
            colunas = list(mock.d[tabela][0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})", [[r[c] for c in colunas] for r in mock.d[tabela]])
    sqlite = SqliteRepository(path)
    atual, base = Periodo(inicio="2025-07", fim="2026-06"), Periodo(inicio="2022-07", fim="2023-06")
    assert cadastro_gd(sqlite, base, atual) == cadastro_gd(mock, base, atual)
    classes = consumo_classes(sqlite, base, atual)
    assert classes == consumo_classes(mock, base, atual)
    kpis = dashboard.kpis(sqlite, base, atual, Filtros(), indicador="executivo")
    assert kpis == dashboard.kpis(mock, base, atual, Filtros(), indicador="executivo")
    assert len(kpis.kpis) == 5
    assert any(k.nome == "UCs faturadas" for k in kpis.kpis)
    energia = next(k.valor_atual for k in kpis.kpis if k.nome == "Energia faturada")
    assert classes.consumo_total_kwh == energia


@pytest.fixture
def client(repo):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[repo_dep] = lambda: repo
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("rota", ["cadastro-gd", "consumo-classes"])
def test_endpoint_respeita_periodos_e_serializa_comparacao_opcional(client, rota):
    resposta = client.get(f"/api/dashboard/{rota}", params={"comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-02"})
    assert resposta.status_code == 200
    if rota == "cadastro-gd":
        assert resposta.json()["atual"]["competencia"] == "2026-02"
        assert resposta.json()["referencia"] is None
    else:
        assert len(resposta.json()["classes"]) == 5
        assert resposta.json()["periodo_base"] is None


@pytest.mark.parametrize("rota", ["cadastro-gd", "consumo-classes"])
@pytest.mark.parametrize("params", [
    {"atual_inicio": "2026-01"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-02", "base_inicio": "2026-02", "base_fim": "2026-03"},
    {"comparar": False, "atual_inicio": "2022-07", "atual_fim": "2026-06"},
])
def test_endpoint_preserva_validacoes_temporais(client, rota, params):
    assert client.get(f"/api/dashboard/{rota}", params=params).status_code == 422
