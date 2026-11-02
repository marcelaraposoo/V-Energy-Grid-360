"""Adaptação dos cálculos A5/A3 ao contrato HTTP existente dos KPIs."""
from decimal import Decimal
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repositories.dashboard import COLUNAS_KPIS, COLUNAS_SEGMENTOS
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.dashboard import router
from app.routers.deps import repo_dep
from app.schemas import Filtros, KpisResponse, Periodo
from app.services.dashboard import kpis
from tests.gold_fixture import criar_gold_db

ATUAL = Periodo(inicio="2026-01", fim="2026-02")
BASE = Periodo(inicio="2025-01", fim="2025-02")


@pytest.fixture
def repo():
    mensais = [
        dict(mes_referencia=mes, receita_energia=receita, consumo_total_kwh=consumo,
             qtd_ucs_faturadas=ucs, inadimplencia_pct=5 if mes < "2026" else 6)
        for mes, receita, consumo, ucs in [
            ("2025-01", 100, 100, 10), ("2025-02", 900, 300, 8),
            ("2026-01", 200, 100, 12), ("2026-02", 1800, 300, 9),
        ]
    ]
    segmentos = []
    for mes in mensais:
        for municipio, classe, fator, ucs in [
            ("Recife", "RESIDENCIAL", Decimal("0.4"), mes["qtd_ucs_faturadas"] // 2),
            ("Olinda", "COMERCIAL", Decimal("0.6"), mes["qtd_ucs_faturadas"] - mes["qtd_ucs_faturadas"] // 2),
        ]:
            receita = Decimal(mes["receita_energia"]) * fator
            total = receita * Decimal("1.2")
            segmentos.append(dict(
                mes_referencia=mes["mes_referencia"], municipio=municipio, bairro="Centro", classe=classe,
                receita_energia=receita, consumo_kwh=Decimal(mes["consumo_total_kwh"]) * fator,
                qtd_ucs_faturadas=ucs, receita_total=total,
                valor_em_aberto=total * Decimal(mes["inadimplencia_pct"]) / 100,
            ))

    def recortar(inicio, fim, municipio=None, bairro=None, classe=None):
        return [r for r in segmentos if inicio <= r["mes_referencia"] <= fim
                and (municipio is None or r["municipio"] == municipio)
                and (bairro is None or r["bairro"] == bairro) and (classe is None or r["classe"] == classe)]

    return SimpleNamespace(
        mensais=mensais, segmentos=segmentos,
        competencias=lambda: [f"{ano}-{mes:02d}" for ano in range(2022, 2027) for mes in range(1, 13)
                             if "2022-07" <= f"{ano}-{mes:02d}" <= "2026-06"],
        municipios_bairros=lambda: {"Recife": ["Centro"], "Olinda": ["Centro"]},
        classes=lambda: {"RESIDENCIAL": "Residencial", "COMERCIAL": "Comercial"},
        kpis_mensais=Mock(side_effect=lambda inicio, fim: [r for r in mensais if inicio <= r["mes_referencia"] <= fim]),
        segmentos_mensais=Mock(side_effect=recortar), indicadores_continuidade=Mock(return_value=[]),
        faturas=Mock(side_effect=AssertionError("KPIs não devem consultar faturas globais")),
    )


def por_nome(resposta):
    return {k.nome: k for k in resposta.kpis}


def test_kpis_globais_usam_acumulados_e_ucs_da_ultima_competencia(repo):
    resposta = kpis(repo, BASE, ATUAL, Filtros())
    itens = por_nome(resposta)
    receita = itens["Receita faturada"]
    assert (receita.valor_atual, receita.valor_base, receita.variacao_abs, receita.variacao_pct) == (2000, 1000, 1000, 100)
    consumo = itens["Energia faturada"]
    assert (consumo.valor_atual, consumo.valor_base, consumo.variacao_abs, consumo.variacao_pct) == (400, 400, 0, 0)
    preco = itens["Tarifa média efetiva"]
    assert (preco.valor_atual, preco.valor_base, preco.variacao_abs, preco.variacao_pct) == (5, 2.5, 2.5, 100)
    ucs = itens["UCs faturadas"]
    assert (ucs.valor_atual, ucs.valor_base, ucs.variacao_abs, ucs.variacao_pct) == (9, 8, 1, 12.5)
    assert itens["Inadimplência"].variacao_pp == 1
    assert len(resposta.kpis) == 7
    assert KpisResponse.model_validate_json(resposta.model_dump_json()) == resposta
    assert repo.kpis_mensais.call_count == repo.segmentos_mensais.call_count == 2
    repo.faturas.assert_not_called()


@pytest.mark.parametrize("filtros", [
    Filtros(municipio="Recife"), Filtros(classe="RESIDENCIAL"),
    Filtros(municipio="Recife", bairro="Centro", classe="RESIDENCIAL"),
])
def test_recortes_usam_a3_sem_repetir_consultas_nem_misturar_bairros_homonimos(repo, filtros):
    itens = por_nome(kpis(repo, BASE, ATUAL, filtros))
    assert itens["Receita faturada"].valor_atual == 800
    assert itens["Energia faturada"].valor_atual == 160
    assert itens["Tarifa média efetiva"].valor_atual == 5
    assert itens["UCs faturadas"].valor_atual == 4
    repo.kpis_mensais.assert_not_called()
    assert repo.segmentos_mensais.call_count == 2
    repo.segmentos_mensais.assert_any_call("2026-01", "2026-02", filtros.municipio, filtros.bairro, filtros.classe)


def test_sem_comparacao_so_consulta_o_periodo_principal(repo):
    itens = por_nome(kpis(repo, None, ATUAL, Filtros()))
    for item in itens.values():
        assert item.valor_base is item.variacao_abs is item.variacao_pct is item.variacao_pp is None
    repo.kpis_mensais.assert_called_once_with("2026-01", "2026-02")
    repo.segmentos_mensais.assert_called_once_with("2026-01", "2026-02", None, None, None)
    repo.indicadores_continuidade.assert_called_once_with("2026-01", "2026-02", municipio=None)


@pytest.mark.parametrize(("ausente", "ucs"), [("2026-01", 9), ("2026-02", None)])
def test_mes_ausente_invalida_totais_e_so_preserva_ucs_quando_mes_final_existe(repo, ausente, ucs):
    repo.mensais[:] = [r for r in repo.mensais if r["mes_referencia"] != ausente]
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros()))
    for nome in ("Receita faturada", "Energia faturada", "Tarifa média efetiva"):
        assert itens[nome].valor_atual is itens[nome].variacao_abs is itens[nome].variacao_pct is None
        assert itens[nome].valor_base is not None
    assert itens["UCs faturadas"].valor_atual == ucs
    # A3 segue completa: a indisponibilidade de A5 não muda o cálculo independente de inadimplência.
    assert itens["Inadimplência"].valor_atual == 6


def test_base_incompleta_nao_compara_totais_parciais(repo):
    repo.mensais.pop(0)
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros()))
    assert itens["Receita faturada"].valor_atual == 2000
    for nome in ("Receita faturada", "Energia faturada", "Tarifa média efetiva"):
        assert itens[nome].valor_base is itens[nome].variacao_abs is itens[nome].variacao_pct is None
    assert itens["UCs faturadas"].variacao_pct == 12.5


def test_mes_ausente_no_recorte_nao_vira_zero(repo):
    repo.segmentos[:] = [r for r in repo.segmentos if not (r["municipio"] == "Recife" and r["mes_referencia"] == "2026-01")]
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros(municipio="Recife")))
    assert itens["Receita faturada"].valor_atual is itens["Energia faturada"].valor_atual is None
    assert itens["Tarifa média efetiva"].valor_atual is None
    assert itens["UCs faturadas"].valor_atual == 4
    assert itens["Inadimplência"].valor_atual is None


def test_nulo_preserva_as_metricas_independentes(repo):
    repo.mensais[2]["consumo_total_kwh"] = None
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros()))
    assert itens["Receita faturada"].valor_atual == 2000
    assert itens["UCs faturadas"].valor_atual == 9
    assert itens["Energia faturada"].valor_atual is itens["Tarifa média efetiva"].valor_atual is None


def test_zeros_validos_preservam_diferenca_absoluta_e_impedem_divisao_por_zero(repo):
    for mes in repo.mensais[:2]:
        mes.update(receita_energia=0, consumo_total_kwh=0, qtd_ucs_faturadas=0)
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros()))
    receita = itens["Receita faturada"]
    assert (receita.valor_base, receita.variacao_abs, receita.variacao_pct) == (0, 2000, None)
    assert itens["Energia faturada"].valor_base == itens["UCs faturadas"].valor_base == 0
    assert itens["Tarifa média efetiva"].valor_base is None


def test_receita_zero_com_consumo_positivo_produz_preco_zero_valido(repo):
    for mes in repo.mensais[2:]:
        mes["receita_energia"] = 0
    itens = por_nome(kpis(repo, BASE, ATUAL, Filtros()))
    assert itens["Tarifa média efetiva"].valor_atual == 0
    assert itens["Tarifa média efetiva"].variacao_pct == -100
    assert itens["Receita faturada"].variacao_pct == -100


def test_preco_preserva_quatro_casas_e_compara_antes_do_arredondamento(repo):
    repo.mensais[0].update(receita_energia=1, consumo_total_kwh=3)
    repo.mensais[3].update(receita_energia=2, consumo_total_kwh=7)
    itens = por_nome(kpis(repo, Periodo(inicio="2025-01", fim="2025-01"),
                         Periodo(inicio="2026-02", fim="2026-02"), Filtros()))
    preco = itens["Tarifa média efetiva"]
    assert (preco.valor_base, preco.valor_atual, preco.variacao_abs, preco.variacao_pct) == (0.3333, 0.2857, -0.0476, -14.29)


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife", bairro="Centro", classe="RESIDENCIAL")])
def test_sqlite_responde_sem_tabela_de_faturas_e_equivale_as_agregadas_do_mock(tmp_path, repo, filtros):
    path = criar_gold_db(tmp_path / "gold.db")
    with sqlite3.connect(path) as con:
        for tabela, colunas, linhas in (
            ("kpis_mensal", COLUNAS_KPIS, repo.mensais),
            ("fato_segmento_mensal", COLUNAS_SEGMENTOS, repo.segmentos),
        ):
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})", [
                [float(r[c]) if isinstance(r.get(c), Decimal) else r.get(c) for c in colunas] for r in linhas
            ])
        con.execute("CREATE TABLE dec_fec_alimentador_mensal (mes_referencia, alimentador, municipio)")
    assert kpis(SqliteRepository(path), BASE, ATUAL, filtros) == kpis(repo, BASE, ATUAL, filtros)


@pytest.fixture
def client(repo):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[repo_dep] = lambda: repo
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("filtros", [{}, {"municipio": "Recife", "bairro": "Centro", "classe": "RESIDENCIAL"}])
def test_endpoint_mantem_contrato_e_parametros_com_calculos_gold(client, filtros):
    resposta = client.get("/api/dashboard/kpis", params={
        "atual_inicio": "2026-01", "atual_fim": "2026-02", "base_inicio": "2025-01", "base_fim": "2025-02", **filtros,
    })
    assert resposta.status_code == 200
    body = resposta.json()
    itens = {k["nome"]: k for k in body["kpis"]}
    assert body["periodo_atual"] == {"inicio": "2026-01", "fim": "2026-02"}
    assert body["periodo_base"] == {"inicio": "2025-01", "fim": "2025-02"}
    assert itens["Receita faturada"]["valor_atual"] == (800 if filtros else 2000)
    assert itens["Receita faturada"]["variacao_pct"] == 100
    assert itens["UCs faturadas"]["valor_atual"] == (4 if filtros else 9)
    assert itens["Inadimplência"]["variacao_pp"] == 1
    assert len(body["kpis"]) == 7


def test_endpoint_sem_comparacao_serializa_nulos_de_um_periodo_incompleto(client, repo):
    repo.mensais.pop(2)
    resposta = client.get("/api/dashboard/kpis", params={
        "comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-02",
    })
    assert resposta.status_code == 200
    assert resposta.json()["periodo_base"] is None
    itens = {k["nome"]: k for k in resposta.json()["kpis"]}
    assert itens["Receita faturada"]["valor_atual"] is None
    assert itens["UCs faturadas"]["valor_atual"] == 9
    for item in itens.values():
        assert item["valor_base"] is item["variacao_abs"] is item["variacao_pct"] is item["variacao_pp"] is None


def test_endpoint_executivo_mantem_ucs_faturadas_sem_consultar_continuidade(client, repo):
    repo.indicadores_continuidade.side_effect = AssertionError("Visão executiva não depende da A8")
    resposta = client.get("/api/dashboard/kpis", params={
        "indicador": "executivo", "comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-02",
    })
    assert resposta.status_code == 200
    assert len(resposta.json()["kpis"]) == 5
    ucs = next(k for k in resposta.json()["kpis"] if k["nome"] == "UCs faturadas")
    assert ucs["valor_atual"] == 9
