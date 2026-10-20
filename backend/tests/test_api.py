import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_filtros():
    j = client.get("/api/filtros").json()
    assert len(j["municipios"]) == 14 and len(j["competencias"]) == 48


def test_variacao_soma_dos_efeitos_fecha():
    for agr in ("municipio", "bairro", "classe"):
        v = client.get(f"/api/receita/variacao?agrupar_por={agr}").json()
        t = v["total"]
        assert t["efeito_preco"] + t["efeito_volume"] == pytest.approx(t["variacao_receita"], abs=1.0)
        assert sum(l["variacao_receita"] for l in v["linhas"]) == pytest.approx(t["variacao_receita"], abs=1.0)


def test_variacao_agrupamento_invalido():
    assert client.get("/api/receita/variacao?agrupar_por=xyz").status_code == 422


def test_kpis():
    j = client.get("/api/dashboard/kpis").json()
    assert {k["nome"] for k in j["kpis"]} >= {"Receita faturada", "Energia faturada"}


def test_visao_360():
    uc = client.get("/api/unidades?limite=1").json()[0]["uc_id"]
    j = client.get(f"/api/unidades/{uc}/visao-360").json()
    assert len(j["consumo"]) == 12 and "mensagem" in j["diagnostico_conta_alta"]
    assert client.get("/api/unidades/UC99999/visao-360").status_code == 404


def test_fila_ordenada_e_fluxo_de_ordem():
    fila = client.get("/api/perdas/fila").json()
    scores = [i["prioridade_score"] for i in fila]
    assert scores == sorted(scores, reverse=True)
    uc = fila[0]["uc_id"]
    o = client.post("/api/perdas/ordens", json={"uc_id": uc}).json()
    assert o["status"] == "PENDENTE"
    assert client.post("/api/perdas/ordens", json={"uc_id": uc}).status_code == 409
    assert uc not in [i["uc_id"] for i in client.get("/api/perdas/fila").json()]
    assert client.post(f"/api/perdas/ordens/{o['id']}/iniciar").json()["status"] == "EM_CAMPO"
    r = client.post(f"/api/perdas/ordens/{o['id']}/resultado", json={"tipo": "fraude", "energia_recuperada_kwh": 120})
    assert r.json()["status"] == "CONCLUIDA"
    assert client.post(f"/api/perdas/ordens/{o['id']}/cancelar").status_code == 409


def test_cancelar_ordem():
    uc = client.get("/api/perdas/fila").json()[0]["uc_id"]
    o = client.post("/api/perdas/ordens", json={"uc_id": uc}).json()
    assert client.post(f"/api/perdas/ordens/{o['id']}/cancelar").json()["status"] == "CANCELADA"


def test_continuidade_ranking_ordenado():
    r = client.get("/api/continuidade/alimentadores").json()
    decs = [x["dec_horas"] for x in r]
    assert decs == sorted(decs, reverse=True) and r[0]["posicao_pior"] == 1
    assert client.get("/api/continuidade/alimentadores/AL999/serie").status_code == 404


def test_ia_stub_e_insights():
    assert client.post("/api/ia/perguntar", json={"pergunta": "teste de pergunta"}).json()["status"] == "nao_implementado"
    assert len(client.get("/api/ia/insights?tela=receita").json()) == 2
