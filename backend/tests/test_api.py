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
    assert client.get("/api/unidades/UC999999/visao-360").status_code == 404


def test_visao_360_comparacao_padrao():
    r = client.get("/api/unidades/UC000001/visao-360")
    assert r.status_code == 200
    diagnostico = r.json()["diagnostico_conta_alta"]
    assert diagnostico["competencia_atual"] == "2026-06"
    assert diagnostico["competencia_referencia"] == "2026-05"
    assert len(diagnostico["competencias_disponiveis"]) == 48


def test_visao_360_seleciona_meses():
    r = client.get("/api/unidades/UC000001/visao-360", params={
        "competencia_atual": "2024-06", "competencia_referencia": "2022-07",
    })
    assert r.status_code == 200
    diagnostico = r.json()["diagnostico_conta_alta"]
    assert diagnostico["competencia_atual"] == "2024-06"
    assert diagnostico["competencia_referencia"] == "2022-07"
    assert diagnostico["consumo"]["variacao_pct"] is not None


@pytest.mark.parametrize("atual", ["2026-05", "2026-06", None])
def test_visao_360_rejeita_referencia_igual_ou_posterior(atual):
    params = {"competencia_referencia": "2026-06"}
    if atual:
        params["competencia_atual"] = atual
    r = client.get("/api/unidades/UC000001/visao-360", params=params)
    assert r.status_code == 422
    assert "referência deve ser anterior" in r.json()["detail"]


@pytest.mark.parametrize("campo", ["competencia_atual", "competencia_referencia"])
@pytest.mark.parametrize("valor", ["2026-13", "06/2026", "", "2020-01"])
def test_visao_360_rejeita_competencia_invalida_ou_sem_historico(campo, valor):
    r = client.get("/api/unidades/UC000001/visao-360", params={campo: valor})
    assert r.status_code == 422


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


def test_obter_ordem_por_id():
    uc = client.get("/api/perdas/fila").json()[0]["uc_id"]
    o = client.post("/api/perdas/ordens", json={"uc_id": uc}).json()
    r = client.get(f"/api/perdas/ordens/{o['id']}")
    assert r.status_code == 200 and r.json()["uc_id"] == uc
    assert client.get("/api/perdas/ordens/999999").status_code == 404
    client.post(f"/api/perdas/ordens/{o['id']}/cancelar")


def test_periodo_invalido_retorna_422():
    assert client.get("/api/dashboard/kpis?base_inicio=2024-05&base_fim=2023-01").status_code == 422
    assert client.get("/api/continuidade/alimentadores?inicio=2026-01&fim=2025-01").status_code == 422


def test_ia_insights_tela_invalida_e_tela_sem_insight():
    assert client.get("/api/ia/insights?tela=xyz").status_code == 422
    assert client.get("/api/ia/insights?tela=perdas").json() == []


def test_ia_limpar_sessao():
    assert client.delete("/api/ia/sessoes/abc").status_code == 204


def test_filtros_desconhecidos_retornam_422():
    assert client.get("/api/dashboard/kpis?municipio=Narnia").status_code == 422
    assert client.get("/api/receita/variacao?classe=Z9").status_code == 422
    assert client.get("/api/receita/variacao?municipio=Olinda&bairro=Boa Viagem").status_code == 422
    assert client.get("/api/receita/variacao?municipio=Recife&bairro=Boa Viagem&classe=B1").status_code == 200


def test_serie_alimentador_404_so_quando_nao_existe():
    assert client.get("/api/continuidade/alimentadores/AL999/serie").status_code == 404
    assert client.get("/api/continuidade/alimentadores/al001/serie").status_code == 200
    assert client.get("/api/continuidade/alimentadores/AL001/serie?inicio=2026-01&fim=2025-01").status_code == 422
    r = client.get("/api/continuidade/alimentadores/AL001/serie?inicio=2030-01&fim=2030-12")
    assert r.status_code == 200 and r.json() == []


def test_cors_aceita_localhost_e_127():
    for origem in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.options("/api/filtros", headers={"Origin": origem, "Access-Control-Request-Method": "GET"})
        assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origem


def test_medidor_sem_ultima_manutencao():
    uc = client.get("/api/unidades?limite=1").json()[0]["uc_id"]
    medidor = client.get(f"/api/unidades/{uc}/visao-360").json()["medidor"]
    assert "ultima_manutencao" not in medidor and "data_instalacao" in medidor
