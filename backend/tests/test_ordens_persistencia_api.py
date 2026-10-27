"""As ordens de inspeção sobrevivem a um reinício da API (testado de ponta a ponta, pelas rotas)."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.ordens_store import SqliteOrdensStore
from app.routers.deps import repo_dep


@pytest.fixture(autouse=True)
def _limpa_override():
    yield
    app.dependency_overrides.pop(repo_dep, None)


def _ligar_api(banco):
    """Simula ligar o servidor: repositório novo apontando para o mesmo arquivo de banco."""
    store = SqliteOrdensStore(str(banco))
    repo = MockRepository(ordens=store)
    app.dependency_overrides[repo_dep] = lambda: repo
    return TestClient(app), store


def test_ordens_sobrevivem_ao_reinicio_da_api(tmp_path):
    banco = tmp_path / "portal.db"

    client, store = _ligar_api(banco)
    uc = client.get("/api/perdas/fila").json()[0]["uc_id"]
    criada = client.post("/api/perdas/ordens", json={"uc_id": uc, "motivo": "queda de consumo"}).json()
    assert client.post(f"/api/perdas/ordens/{criada['id']}/iniciar").json()["status"] == "EM_CAMPO"
    store.close()

    client, store = _ligar_api(banco)  # servidor reiniciado
    lista = client.get("/api/perdas/ordens").json()
    assert [o["id"] for o in lista] == [criada["id"]]
    assert lista[0]["status"] == "EM_CAMPO" and lista[0]["motivo"] == "queda de consumo"
    na_fila = [i["uc_id"] for i in client.get("/api/perdas/fila", params={"tamanho": 100}).json()]
    assert uc not in na_fila  # a UC continua fora da fila: ainda tem ordem ativa
    assert client.post("/api/perdas/ordens", json={"uc_id": uc}).status_code == 409
    r = client.post(f"/api/perdas/ordens/{criada['id']}/resultado", json={"tipo": "fraude", "energia_recuperada_kwh": 120})
    assert r.json()["status"] == "CONCLUIDA"
    store.close()

    client, store = _ligar_api(banco)  # e mais um reinício
    final = client.get(f"/api/perdas/ordens/{criada['id']}").json()
    assert final["status"] == "CONCLUIDA" and final["resultado"]["tipo"] == "fraude"
    assert final["resultado"]["energia_recuperada_kwh"] == 120
    store.close()


def test_ids_de_ordens_nao_se_repetem_entre_reinicios(tmp_path):
    banco = tmp_path / "portal.db"
    client, store = _ligar_api(banco)
    fila = client.get("/api/perdas/fila", params={"tamanho": 100}).json()
    primeira = client.post("/api/perdas/ordens", json={"uc_id": fila[0]["uc_id"]}).json()
    store.close()

    client, store = _ligar_api(banco)
    segunda = client.post("/api/perdas/ordens", json={"uc_id": fila[1]["uc_id"]}).json()
    assert segunda["id"] == primeira["id"] + 1
    store.close()
