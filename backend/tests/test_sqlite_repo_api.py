"""A API com DATA_SOURCE=sqlite: o que já responde com a dim_uc e o que devolve 501 até a Gold entregar as fatos.

Troca o repositório pela dependência `repo_dep` (sem mexer em variável de ambiente nem no cache do get_repo).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.ordens_store import MemoriaOrdensStore
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from tests.gold_fixture import criar_gold_db


@pytest.fixture
def client(tmp_path):
    repo = SqliteRepository(criar_gold_db(tmp_path / "gold.db"), ordens=MemoriaOrdensStore())
    app.dependency_overrides[repo_dep] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_filtros_saem_da_dim_uc(client):
    j = client.get("/api/filtros").json()
    assert [m["nome"] for m in j["municipios"]] == ["OLINDA", "PAULISTA", "RECIFE"]
    assert "PODER PUBLICO" in [c["codigo"] for c in j["classes"]]
    assert len(j["alimentadores"]) == 3 and len(j["competencias"]) == 48


def test_busca_de_unidades_pelo_nome_mascarado(client):
    r = client.get("/api/unidades", params={"q": "jose a"})
    assert r.status_code == 200 and [u["uc_id"] for u in r.json()] == ["UC00002"]


def test_dashboard_devolve_501_explicando_a_tabela_que_falta(client):
    r = client.get("/api/dashboard/kpis")
    assert r.status_code == 501 and "fato_consumo_faturamento" in r.json()["detail"]


def test_filtro_aceita_classe_real_da_gold(client):
    # 501 (e não 422) mostra que "PODER PUBLICO" passou na validação contra o catálogo
    assert client.get("/api/dashboard/kpis", params={"classe": "PODER PUBLICO"}).status_code == 501
    assert client.get("/api/dashboard/kpis", params={"classe": "B1"}).status_code == 422


def test_fila_de_perdas_devolve_501_ate_existir_fila_inspecao(client):
    r = client.get("/api/perdas/fila")
    assert r.status_code == 501 and "fila_inspecao" in r.json()["detail"]
