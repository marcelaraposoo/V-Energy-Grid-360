"""Paridade do cadastro público com dim_uc, sem usar a exportação oficial da Gold."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.schemas import CadastroUC
from app.services.perdas import fila
from tests.gold_fixture import COLUNAS, criar_gold_db


CLASSES = {
    "RESIDENCIAL": "B1", "RURAL": "B2", "COMERCIAL": "B3",
    "PODER PUBLICO": "B3", "INDUSTRIAL": "A4",
}


@pytest.fixture(scope="module")
def mock():
    return MockRepository()


@pytest.fixture(scope="module")
def sqlite(mock, tmp_path_factory):
    path = tmp_path_factory.mktemp("cadastro-gold") / "gold.db"
    return SqliteRepository(criar_gold_db(path, ucs=mock.d["dim_uc"]))


def test_cadastro_preserva_classe_subgrupo_e_flag_gd_nos_dois_adaptadores(mock, sqlite):
    for original in mock.d["dim_uc"]:
        uc_id = original["id_uc"]
        cadastros = [CadastroUC.model_validate(repo.uc(uc_id)) for repo in (mock, sqlite)]
        assert cadastros[0] == cadastros[1]
        for cadastro in cadastros:
            assert cadastro.classe == original["classe"]
            assert cadastro.subgrupo_tarifario == original["subgrupo_tarifario"]
            assert cadastro.subgrupo_tarifario == CLASSES[cadastro.classe]
            assert cadastro.possui_gd is original["possui_gd"]


def test_catalogo_e_busca_distinguem_comercial_de_poder_publico(mock, sqlite):
    assert mock.classes() == sqlite.classes()
    assert set(mock.classes()) == set(CLASSES)
    for classe in CLASSES:
        encontrados = []
        for repo in (mock, sqlite):
            ucs = repo.buscar_ucs(None, None, classe, 1000)
            assert ucs
            assert {u["classe"] for u in ucs} == {classe}
            assert {u["subgrupo_tarifario"] for u in ucs} == {CLASSES[classe]}
            encontrados.append({u["uc_id"] for u in ucs})
        assert encontrados[0] == encontrados[1]


@pytest.mark.parametrize("classe", CLASSES)
def test_faturas_e_fila_continuam_filtrando_por_classe_da_gold(mock, classe, monkeypatch):
    por_classe = {u["classe"]: u for u in mock.d["dim_uc"]}
    suspeitas = [{
        "uc_id": u["id_uc"], "probabilidade": 0.9,
        "energia_recuperavel_kwh_mes": 100, "motivos": ["Cenário fictício de teste"],
    } for u in por_classe.values()]
    monkeypatch.setattr(mock, "suspeitas", lambda: suspeitas)
    itens, total = fila(mock, classe=classe, tamanho=1000)
    assert total == 1
    assert itens[0].uc_id == por_classe[classe]["id_uc"]
    assert {item.classe for item in itens} == {classe}
    faturas = mock.faturas("2025-07", "2026-06", classe=classe)
    assert faturas
    assert {f["classe"] for f in faturas} == {classe}


@pytest.mark.parametrize(("valor", "esperado"), [
    (0, False), (1, True), ("false", False), ("true", True), ("f", False), ("t", True),
    (None, None),
])
def test_sqlite_preserva_booleano_sem_confundir_falso_com_indisponivel(mock, tmp_path, valor, esperado):
    original = {**mock.d["dim_uc"][0], "possui_gd": valor}
    repo = SqliteRepository(criar_gold_db(tmp_path / "gold.db", ucs=[original]))
    cadastro = CadastroUC.model_validate(repo.uc(original["id_uc"]))
    assert cadastro.possui_gd is esperado


def test_colunas_opcionais_ausentes_nao_inventam_subgrupo_ou_ausencia_de_gd(mock, tmp_path):
    colunas = [c for c in COLUNAS if c not in {"possui_gd", "subgrupo_tarifario"}]
    original = mock.d["dim_uc"][0]
    repo = SqliteRepository(criar_gold_db(tmp_path / "gold.db", ucs=[original], colunas=colunas))
    cadastro = CadastroUC.model_validate(repo.uc(original["id_uc"]))
    assert cadastro.classe == original["classe"]
    assert cadastro.subgrupo_tarifario is None
    assert cadastro.possui_gd is None


@pytest.mark.parametrize(("campo", "valor"), [("classe", "B1"), ("subgrupo_tarifario", "RESIDENCIAL")])
def test_modelo_nao_aceita_trocar_os_dois_conceitos(mock, campo, valor):
    cadastro = mock.uc("UC000001")
    cadastro[campo] = valor
    with pytest.raises(ValidationError):
        CadastroUC.model_validate(cadastro)


@pytest.mark.parametrize("adaptador", ["mock", "sqlite"])
def test_endpoint_busca_preserva_campos_do_cadastro(mock, sqlite, adaptador):
    repo = mock if adaptador == "mock" else sqlite
    app.dependency_overrides[repo_dep] = lambda: repo
    try:
        with TestClient(app) as client:
            r = client.get("/api/unidades", params={"classe": "PODER PUBLICO", "limite": 100})
            assert r.status_code == 200 and r.json()
            for cadastro in r.json():
                assert cadastro["classe"] == "PODER PUBLICO"
                assert cadastro["subgrupo_tarifario"] == "B3"
                assert type(cadastro["possui_gd"]) is bool
    finally:
        app.dependency_overrides.pop(repo_dep, None)
