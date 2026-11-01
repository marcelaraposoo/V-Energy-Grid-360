"""Contrato HTTP do card, com o mesmo roteador e dependências do Dashboard."""
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repositories.mock_repo import MockRepository
from app.routers.dashboard import router
from app.routers.deps import repo_dep


@pytest.fixture(scope="module")
def repo():
    return MockRepository()


@pytest.fixture
def client(repo):
    app = FastAPI()
    app.include_router(router)

    async def repository_override():
        return repo

    app.dependency_overrides[repo_dep] = repository_override
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(("inicio", "fim", "comparar"), [
    ("2026-05", "2026-05", False), ("2026-05", "2026-05", True),
    ("2026-01", "2026-06", False), ("2026-01", "2026-06", True),
])
def test_endpoint_entrega_os_quatro_modos_sem_dependencias_dos_outros_kpis(client, repo, monkeypatch, inicio, fim, comparar):
    monkeypatch.setattr(repo, "faturas", Mock(side_effect=AssertionError("Não consultar outros KPIs")))
    resposta = client.get("/api/dashboard/kpis", params={
        "indicador": "inadimplencia", "comparar": comparar, "atual_inicio": inicio, "atual_fim": fim,
    })
    assert resposta.status_code == 200
    body = resposta.json()
    kpi, = body["kpis"]
    assert kpi["nome"] == "Inadimplência"
    assert kpi["variacao_pct"] is kpi["variacao_abs"] is None
    assert kpi["inadimplencia"]["ultima_competencia"] == fim
    assert kpi["inadimplencia"]["data_corte"] == "2026-06-30"
    if inicio == fim:
        assert kpi["valor_atual"] == kpi["inadimplencia"]["ultima_competencia_pct"]
    if comparar:
        assert body["periodo_base"] is not None and kpi["variacao_pp"] is not None
    else:
        assert body["periodo_base"] is kpi["valor_base"] is kpi["variacao_pp"] is None


def test_endpoint_preserva_os_tres_filtros_e_consulta_somente_os_segmentos_pedidos(client, repo, monkeypatch):
    original = repo.segmentos_mensais
    leitura = Mock(wraps=original)
    monkeypatch.setattr(repo, "segmentos_mensais", leitura)
    resposta = client.get("/api/dashboard/kpis", params={
        "indicador": "inadimplencia", "comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-06",
        "municipio": "Recife", "bairro": "Boa Viagem", "classe": "PODER PUBLICO",
    })
    assert resposta.status_code == 200
    leitura.assert_called_once_with("2026-01", "2026-06", "Recife", "Boa Viagem", "PODER PUBLICO")


@pytest.mark.parametrize("params", [
    {"indicador": "invalido"},
    {"comparar": False, "base_inicio": "2025-01", "base_fim": "2025-06"},
    {"atual_inicio": "2026-01"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-06", "base_inicio": "2026-02", "base_fim": "2026-03"},
    {"comparar": False, "atual_inicio": "2022-07", "atual_fim": "2026-06"},
    {"municipio": "desconhecido"},
])
def test_endpoint_mantem_validacoes_temporais_e_de_filtros(client, params):
    resposta = client.get("/api/dashboard/kpis", params={"indicador": "inadimplencia", **params})
    assert resposta.status_code == 422


def test_endpoint_serializa_lacunas_como_null_e_preserva_ultima_taxa(client, repo, monkeypatch):
    original = repo.segmentos_mensais
    monkeypatch.setattr(repo, "segmentos_mensais", lambda *args: [
        r for r in original(*args) if r["mes_referencia"] != "2026-01"
    ])
    resposta = client.get("/api/dashboard/kpis", params={
        "indicador": "inadimplencia", "comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-06",
    })
    assert resposta.status_code == 200
    kpi, = resposta.json()["kpis"]
    assert kpi["valor_atual"] is kpi["variacao_pp"] is None
    assert kpi["inadimplencia"]["competencias_ausentes"] == ["2026-01"]
    assert kpi["inadimplencia"]["ultima_competencia_pct"] == 100
