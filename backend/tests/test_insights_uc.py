from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_insights_da_uc_retorna_lista():
    r = client.get("/api/ia/insights/uc/UC000114")
    assert r.status_code == 200
    for item in r.json():
        assert item["tipo"] in ("destaque", "alerta", "informativo")
        assert "uc_id" not in item["dados"]


def test_insights_de_uc_inexistente_nao_e_200():
    assert client.get("/api/ia/insights/uc/NAO_EXISTE").status_code in (404, 422)
