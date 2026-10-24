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


# ---------- fila: busca e paginação ----------
def _fila(**params):
    r = client.get("/api/perdas/fila", params=params)
    assert r.status_code == 200, r.text
    return r.json(), int(r.headers["X-Total-Count"])


def test_fila_paginacao_cobre_tudo_sem_repetir():
    tudo, total = _fila(tamanho=100)
    assert total == len(tudo) and total > 10
    paginas, pagina = [], 1
    while True:
        itens, t = _fila(pagina=pagina, tamanho=7)
        assert t == total
        if not itens:
            break
        assert len(itens) <= 7
        paginas += itens
        pagina += 1
    assert [i["uc_id"] for i in paginas] == [i["uc_id"] for i in tudo]
    assert [i["posicao"] for i in paginas] == list(range(1, total + 1))


def test_fila_pagina_alem_do_fim_devolve_lista_vazia_com_total():
    _, total = _fila()
    itens, t = _fila(pagina=999)
    assert itens == [] and t == total


def test_fila_busca_por_uc_e_titular_sem_acento_nem_caixa():
    tudo, total = _fila(tamanho=100)
    alvo = tudo[3]
    por_uc, _ = _fila(q=alvo["uc_id"].lower())
    assert alvo["uc_id"] in [i["uc_id"] for i in por_uc]
    nome = alvo["titular"].split()[0].upper()
    por_nome, t = _fila(q=nome, tamanho=100)
    assert t == len(por_nome) and 1 <= t <= total
    assert all(nome.lower() in i["titular"].lower() or nome.lower() in i["uc_id"].lower() for i in por_nome)
    vazio, t0 = _fila(q="zzzz-nao-existe")
    assert vazio == [] and t0 == 0


def test_fila_busca_combina_com_filtros_e_mantem_posicao_na_fila_filtrada():
    tudo, _ = _fila(tamanho=100)
    mun = tudo[0]["municipio"]
    so_mun, t = _fila(municipio=mun, tamanho=100)
    assert t == len(so_mun) and all(i["municipio"] == mun for i in so_mun)
    assert [i["posicao"] for i in so_mun] == list(range(1, t + 1))


def test_fila_parametros_invalidos_retornam_422():
    for params in ({"pagina": 0}, {"tamanho": 0}, {"tamanho": 101}, {"prob_minima": 2}, {"q": "x" * 101}):
        assert client.get("/api/perdas/fila", params=params).status_code == 422


def test_fila_expoe_total_para_o_navegador_via_cors():
    r = client.get("/api/perdas/fila", headers={"Origin": "http://localhost:5173"})
    assert "x-total-count" in r.headers["access-control-expose-headers"].lower()


def test_normalizar_remove_acento_e_caixa():
    from app.services.perdas import normalizar
    assert normalizar("  João ÁLVARO ") == "joao alvaro"


# ---------- ordens: transições inválidas e mensagens de erro ----------
def _nova_ordem(indice=0):
    uc = client.get("/api/perdas/fila", params={"tamanho": 100}).json()[indice]["uc_id"]
    r = client.post("/api/perdas/ordens", json={"uc_id": uc})
    assert r.status_code == 201, r.text
    return r.json()


def _acao(oid, acao, corpo=None):
    return client.post(f"/api/perdas/ordens/{oid}/{acao}", json=corpo) if corpo else client.post(f"/api/perdas/ordens/{oid}/{acao}")


def test_ordem_concluida_nao_aceita_nenhuma_acao():
    oid = _nova_ordem()["id"]
    assert _acao(oid, "iniciar").json()["status"] == "EM_CAMPO"
    repetida = _acao(oid, "iniciar")
    assert repetida.status_code == 409 and "PENDENTES" in repetida.json()["detail"] and "EM_CAMPO" in repetida.json()["detail"]
    assert _acao(oid, "resultado", {"tipo": "nenhuma"}).json()["status"] == "CONCLUIDA"
    for acao, corpo in (("iniciar", None), ("resultado", {"tipo": "fraude"}), ("cancelar", None)):
        r = _acao(oid, acao, corpo)
        assert r.status_code == 409, acao
        assert f"ordem {oid}" in r.json()["detail"] and "CONCLUIDA" in r.json()["detail"], acao


def test_ordem_cancelada_nao_aceita_nenhuma_acao():
    oid = _nova_ordem(1)["id"]
    assert _acao(oid, "cancelar").json()["status"] == "CANCELADA"
    for acao, corpo in (("iniciar", None), ("resultado", {"tipo": "fraude"}), ("cancelar", None)):
        r = _acao(oid, acao, corpo)
        assert r.status_code == 409 and "CANCELADA" in r.json()["detail"], acao


def test_ordem_pode_ser_cancelada_ou_concluida_direto_de_pendente_e_em_campo():
    a = _nova_ordem(2)["id"]
    assert _acao(a, "resultado", {"tipo": "erro_cadastro", "energia_recuperada_kwh": 10}).json()["status"] == "CONCLUIDA"
    b = _nova_ordem(2)["id"]
    _acao(b, "iniciar")
    assert _acao(b, "cancelar").json()["status"] == "CANCELADA"


def test_acoes_em_ordem_inexistente_retornam_404():
    for acao, corpo in (("iniciar", None), ("resultado", {"tipo": "nenhuma"}), ("cancelar", None)):
        r = _acao(999999, acao, corpo)
        assert r.status_code == 404 and "999999" in r.json()["detail"], acao


def test_ordem_duplicada_na_mesma_uc_retorna_409_e_resultado_invalido_retorna_422():
    o = _nova_ordem(3)
    dup = client.post("/api/perdas/ordens", json={"uc_id": o["uc_id"]})
    assert dup.status_code == 409 and "ativa" in dup.json()["detail"]
    assert _acao(o["id"], "resultado", {"tipo": "invalido"}).status_code == 422
    assert _acao(o["id"], "resultado", {"tipo": "fraude", "energia_recuperada_kwh": -5}).status_code == 422
    assert client.get(f"/api/perdas/ordens/{o['id']}").json()["status"] == "PENDENTE"
    _acao(o["id"], "cancelar")
