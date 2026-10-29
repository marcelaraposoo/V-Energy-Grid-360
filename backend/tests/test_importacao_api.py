"""Modelo e importação da planilha de resultados: o ciclo que a equipe de campo faz fora do portal."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
MODELO = "/api/perdas/ordens/resultados/modelo"
IMPORTAR = "/api/perdas/ordens/resultados/importar"
CAB = "ordem_id;tipo;energia_recuperada_kwh;observacoes"


def _nova_ordem() -> dict:
    # Quem já tem ordem ativa sai da fila, então o primeiro da fila é sempre uma UC livre.
    uc = client.get("/api/perdas/fila").json()[0]["uc_id"]
    r = client.post("/api/perdas/ordens", json={"uc_id": uc, "motivo": "teste de importação"})
    assert r.status_code == 201
    return r.json()


def _enviar(*linhas: str):
    corpo = ("\r\n".join(linhas) + "\r\n").encode("utf-8")
    return client.post(IMPORTAR, content=corpo, headers={"Content-Type": "text/csv"})


def test_modelo_e_um_csv_com_as_ordens_em_aberto():
    ordem = _nova_ordem()
    r = client.get(MODELO)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith('attachment; filename="resultados-inspecao-')
    assert f"{ordem['id']};{ordem['uc_id']};" in r.content.decode("utf-8-sig")


def test_modelo_nao_e_confundido_com_o_id_de_uma_ordem():
    assert client.get(MODELO).status_code == 200  # /ordens/{ordem_id} exigiria um inteiro (422)


def test_importar_registra_o_resultado_e_conclui_a_ordem():
    ordem = _nova_ordem()
    r = _enviar(CAB, f"{ordem['id']};fraude;150,5;medidor violado")
    assert r.status_code == 200
    resumo = r.json()
    assert (resumo["total"], resumo["aceitas"], resumo["rejeitadas"]) == (1, 1, [])
    atual = client.get(f"/api/perdas/ordens/{ordem['id']}").json()
    assert atual["status"] == "CONCLUIDA"
    assert atual["resultado"]["tipo"] == "fraude"
    assert atual["resultado"]["energia_recuperada_kwh"] == 150.5


def test_linha_com_erro_nao_derruba_as_outras():
    boa, outra = _nova_ordem(), _nova_ordem()
    r = _enviar(CAB, f"{boa['id']};nenhuma;;", f"{outra['id']};estranho;;", "99999999;fraude;1;")
    resumo = r.json()
    assert resumo["aceitas"] == 1
    erros = {x["linha"]: x for x in resumo["rejeitadas"]}
    assert "desconhecido" in erros[3]["erro"]
    assert erros[4]["ordem_id"] == 99999999  # ordem que não existe
    assert client.get(f"/api/perdas/ordens/{outra['id']}").json()["status"] == "PENDENTE"


def test_ordem_ja_concluida_e_rejeitada_e_linha_sem_preenchimento_e_ignorada():
    concluida, pendente = _nova_ordem(), _nova_ordem()
    assert _enviar(CAB, f"{concluida['id']};nenhuma;;").json()["aceitas"] == 1
    resumo = _enviar(CAB, f"{concluida['id']};fraude;5;", f"{pendente['id']};;;").json()
    assert resumo["aceitas"] == 0 and resumo["ignoradas"] == 1
    assert len(resumo["rejeitadas"]) == 1 and "CONCLUIDA" in resumo["rejeitadas"][0]["erro"]


def test_arquivo_sem_as_colunas_obrigatorias_devolve_422_com_mensagem():
    r = _enviar("coluna_a;coluna_b", "1;2")
    assert r.status_code == 422
    assert "ordem_id" in r.json()["detail"]


def test_arquivo_vazio_devolve_422():
    assert client.post(IMPORTAR, content=b"", headers={"Content-Type": "text/csv"}).status_code == 422
