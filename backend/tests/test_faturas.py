"""Mesmas regras e paginação nos adaptadores mock e SQLite, sem depender da Gold real."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoEncontrado, NaoDisponivelNaGold
from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.services.faturas import listar
from app.services.unidades import visao_360
from tests.gold_fixture import criar_gold_db


@pytest.fixture(params=["mock", "sqlite"])
def repo(request, tmp_path, monkeypatch):
    mock = MockRepository()
    original = mock._faturas_por_uc["UC000001"][0]
    casos = [("PAGA", 91, "MAIS DE 90 DIAS"), ("PAGA", 0, "EM DIA"),
             ("EM ABERTO", 0, "EM DIA"), ("EM ABERTO", 1, "ATE 30 DIAS"),
             ("EM ABERTO", 30, "ATE 30 DIAS"), ("EM ABERTO", 31, "31 A 90 DIAS"),
             ("EM ABERTO", 90, "31 A 90 DIAS"), ("EM ABERTO", 91, "MAIS DE 90 DIAS")]
    linhas = []
    for i in range(30):
        status, dias, faixa = casos[i % len(casos)]
        linhas.append({**original, "mes_referencia": f"{2024 + i // 12}-{i % 12 + 1:02d}",
                       "id_fatura": f"F{i:02d}", "status_fatura": status, "dias_atraso": dias,
                       "faixa_atraso": faixa, "em_aberto": status == "EM ABERTO",
                       "data_pagamento": "2026-06-01" if status == "PAGA" else None})
    linhas.reverse()
    # Uma dívida de outra UC não pode entrar nos totais nem na página.
    outra = {**linhas[0], "id_uc": "UC000002", "id_fatura": "OUTRA", "status_fatura": "EM ABERTO", "faixa_atraso": "MAIS DE 90 DIAS"}
    if request.param == "mock":
        monkeypatch.setitem(mock._faturas_por_uc, "UC000001", linhas)
        monkeypatch.setitem(mock._faturas_por_uc, "UC000002", [outra])
        monkeypatch.setitem(mock._faturas_por_uc, "UC000003", [])
        # A consulta paginada deve mapear só a página, sem recorrer ao histórico público completo.
        monkeypatch.setattr(mock, "faturas_uc", lambda _: pytest.fail("carregou todo o histórico"))
        return mock
    path = criar_gold_db(tmp_path / "gold.db", ucs=[mock._ucs[uc] for uc in ["UC000001", "UC000002", "UC000003"]])
    with sqlite3.connect(path) as con:
        colunas = list(original)
        con.execute(f"CREATE TABLE fato_consumo_faturamento ({', '.join(colunas)})")
        con.executemany(f"INSERT INTO fato_consumo_faturamento VALUES ({', '.join('?' for _ in colunas)})",
                        [[linha[c] for c in colunas] for linha in [*linhas, outra]])
    return SqliteRepository(path)


def test_recentes_limita_12_competencias_e_exclui_so_abertas_antigas(repo):
    primeira = listar(repo, "UC000001", "recentes", None, "todas", 1)
    segunda = listar(repo, "UC000001", "recentes", None, "todas", 2)
    assert primeira.total == 11
    assert [f.id_fatura for f in primeira.itens] == [f"F{i:02d}" for i in [29, 28, 27, 26, 25, 24, 22, 21, 20, 19]]
    assert [f.id_fatura for f in segunda.itens] == ["F18"]
    assert primeira.resumo.pendencias_recentes == 19
    assert primeira.resumo.pendencias_antigas == 3
    assert primeira.resumo == segunda.resumo


def test_historico_em_aberto_preserva_pendencias_antigas_de_outros_anos(repo):
    faturas = [f for pagina in [1, 2, 3]
               for f in listar(repo, "UC000001", "historico", None, "em_aberto", pagina).itens]
    antigas = [f for f in faturas if f.faixa_atraso == "MAIS DE 90 DIAS"]
    assert [f.id_fatura for f in antigas] == ["F23", "F15", "F07"]
    assert all(f.status != "paga" for f in faturas)


def test_historico_paginado_sem_repeticoes_e_resumo_independente(repo):
    paginas = [listar(repo, "uc000001", "historico", None, "todas", p) for p in [1, 2, 3, 4]]
    assert [len(p.itens) for p in paginas] == [10, 10, 10, 0]
    assert all(p.total == 30 and p.tamanho == 10 for p in paginas)
    assert [f.id_fatura for p in paginas for f in p.itens] == [f"F{i:02d}" for i in reversed(range(30))]
    assert all(p.resumo == paginas[0].resumo for p in paginas)
    assert paginas[0].anos_disponiveis == [2026, 2025, 2024]


@pytest.mark.parametrize(("ano", "situacao", "indices"), [
    (2024, "paga", [9, 8, 1, 0]), (2026, "em_aberto", [29, 28, 27, 26]),
    (2026, "todas", [29, 28, 27, 26, 25, 24]), (2020, "todas", []),
])
def test_filtros_historico_nao_alteram_totais_nem_catalogo(repo, ano, situacao, indices):
    resultado = listar(repo, "UC000001", "historico", ano, situacao, 1)
    assert [f.id_fatura for f in resultado.itens] == [f"F{i:02d}" for i in indices]
    assert resultado.total == len(indices)
    assert resultado.resumo.model_dump() == {"pendencias_recentes": 19, "pendencias_antigas": 3}
    assert resultado.anos_disponiveis == [2026, 2025, 2024]


def test_uc_sem_faturas_e_uc_inexistente(repo):
    sem_historico = listar(repo, "UC000003", "historico", None, "todas", 1)
    assert sem_historico.itens == [] and sem_historico.total == 0
    assert sem_historico.anos_disponiveis == []
    assert sem_historico.resumo.model_dump() == {"pendencias_recentes": 0, "pendencias_antigas": 0}
    resultado = listar(repo, "UC000002", "recentes", None, "todas", 1)
    assert resultado.itens == [] and resultado.total == 0
    assert resultado.resumo.pendencias_antigas == 1
    with pytest.raises(NaoEncontrado):
        listar(repo, "UC999999", "recentes", None, "todas", 1)


def test_visao_360_nao_envia_todas_as_pendencias():
    repo = MockRepository()
    resposta = visao_360(repo, "UC000001").model_dump(mode="json")
    assert "faturas_em_aberto" not in resposta
    assert len(resposta["faturas"]) == 1
    assert resposta["resumo_faturas"] == repo.pagina_faturas_uc("UC000001", "historico", None, "todas", 1)["resumo"]


def test_sqlite_sem_fato_informa_indisponibilidade(tmp_path):
    repo = SqliteRepository(criar_gold_db(tmp_path / "gold.db"))
    with pytest.raises(NaoDisponivelNaGold):
        listar(repo, "UC00001", "recentes", None, "todas", 1)


@pytest.fixture
def client(repo):
    app.dependency_overrides[repo_dep] = lambda: repo
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(repo_dep, None)


def test_endpoint_pagina_e_detalhes_inclui_tributos(client):
    resposta = client.get("/api/unidades/UC000001/faturas")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total"] == 11 and dados["pagina"] == 1 and dados["tamanho"] == 10
    assert len(dados["itens"]) == 10
    assert {"valor_energia", "valor_total", "tributos", "bandeira", "faixa_atraso"} <= dados["itens"][0].keys()
    assert client.get("/api/unidades/UC999999/faturas").status_code == 404


@pytest.mark.parametrize("params", [
    {"pagina": 0}, {"pagina": -1}, {"aba": "invalida"}, {"situacao": "atrasada"},
    {"aba": "historico", "ano": "abc"}, {"aba": "historico", "ano": 10000},
    {"ano": 2024}, {"situacao": "paga"}, {"aba": "antigas"},
])
def test_endpoint_rejeita_filtros_invalidos(client, params):
    assert client.get("/api/unidades/UC000001/faturas", params=params).status_code == 422
