"""GET /api/perdas/fila/exportar: o arquivo que o gerente de perdas envia à equipe de campo."""
import csv
import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _linhas(resposta):
    texto = resposta.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto, newline=""), delimiter=";"))


def test_exportar_devolve_arquivo_csv_para_download():
    r = client.get("/api/perdas/fila/exportar")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith('attachment; filename="fila-inspecao-')
    assert r.headers["content-disposition"].endswith('.csv"')
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM: o Excel abre com os acentos certos


def test_exportar_traz_a_fila_inteira_ordenada_e_o_total_no_cabecalho():
    fila = client.get("/api/perdas/fila", params={"tamanho": 100}).json()
    r = client.get("/api/perdas/fila/exportar")
    [cabecalho, *dados] = _linhas(r)
    assert cabecalho[:2] == ["Posição", "UC"]
    assert [d[1] for d in dados] == [i["uc_id"] for i in fila]
    assert [int(d[0]) for d in dados] == list(range(1, len(fila) + 1))
    assert r.headers["x-total-count"] == str(len(fila))


def test_exportar_respeita_filtros_e_limite():
    fila = client.get("/api/perdas/fila", params={"tamanho": 100}).json()
    municipio = fila[0]["municipio"]
    do_municipio = [i for i in fila if i["municipio"] == municipio]
    r = client.get("/api/perdas/fila/exportar", params={"municipio": municipio})
    dados = _linhas(r)[1:]
    assert len(dados) == len(do_municipio) and {d[3] for d in dados} == {municipio}

    curto = client.get("/api/perdas/fila/exportar", params={"limite": 3})
    assert len(_linhas(curto)) == 1 + 3
    assert curto.headers["x-total-count"] == str(len(fila))  # o total é da fila, não do arquivo


def test_exportar_nao_inclui_uc_com_ordem_ativa():
    uc = client.get("/api/perdas/fila").json()[0]["uc_id"]
    ordem = client.post("/api/perdas/ordens", json={"uc_id": uc}).json()
    try:
        ucs = [d[1] for d in _linhas(client.get("/api/perdas/fila/exportar"))[1:]]
        assert uc not in ucs
    finally:
        client.post(f"/api/perdas/ordens/{ordem['id']}/cancelar")


def test_exportar_valida_parametros():
    assert client.get("/api/perdas/fila/exportar", params={"limite": 0}).status_code == 422
    assert client.get("/api/perdas/fila/exportar", params={"limite": 5001}).status_code == 422
    assert client.get("/api/perdas/fila/exportar", params={"prob_minima": 2}).status_code == 422


def test_navegador_consegue_ler_o_nome_do_arquivo_via_cors():
    r = client.get("/api/perdas/fila/exportar", headers={"Origin": "http://localhost:5173"})
    expostos = r.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in expostos and "x-total-count" in expostos
