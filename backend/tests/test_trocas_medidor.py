"""A6, sinalização da A2 e Visão 360 com SQLite exclusivamente fictício."""
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoDisponivelNaGold
from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.schemas import TrocaMedidorUC
from app.services.unidades import visao_360
from tests.gold_fixture import criar_gold_db


@pytest.fixture
def cenario(tmp_path):
    mock = MockRepository()
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        for tabela in ("fato_consumo_faturamento", "fato_troca_medidor", "fato_interrupcao",
                       "dec_fec_alimentador_mensal", "fato_atendimento"):
            linhas = mock.d[tabela]
            colunas = list(linhas[0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                            [[r[c] for c in colunas] for r in reversed(linhas)])
    return SimpleNamespace(mock=mock, repo=SqliteRepository(path), path=path)


def test_mock_a6_coerente_com_dim_e_a2_sem_incluir_mes_da_troca():
    repo = MockRepository()
    trocas = repo.d["fato_troca_medidor"]
    assert {t["mes_troca"] for t in trocas} == {"2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"}
    assert len({t["id_uc"] for t in trocas}) == len(trocas)
    for troca in trocas:
        assert TrocaMedidorUC.model_validate(troca).model_dump() == troca
        uc = repo._ucs[troca["id_uc"]]
        assert uc["medidor_trocado_recentemente"] is True
        assert troca["id_medidor_novo"] == uc["id_medidor_ativo"] != troca["id_medidor_antigo"]
        assert troca["tipo_medidor_novo"] == uc["tipo_medidor_ativo"]
        assert uc["data_instalacao_medidor"][:7] == troca["mes_troca"]
        assert (troca["classe"], troca["municipio"], troca["bairro"]) == (uc["classe"], uc["municipio"], uc["bairro"])
        fatos = sorted(repo._faturas_por_uc[uc["id_uc"]], key=lambda f: f["mes_referencia"])
        indice = next(i for i, f in enumerate(fatos) if f["troca_medidor"])
        assert fatos[indice]["mes_referencia"] == troca["mes_troca"]
        assert sum(f["troca_medidor"] for f in fatos) == 1
        antes = [f["consumo_kwh"] for f in fatos[indice - 6:indice]]
        depois = [f["consumo_kwh"] for f in fatos[indice + 1:indice + 7]]
        assert 3 <= len(depois) <= 6
        assert troca["consumo_medio_6m_antes"] == round(sum(antes) / len(antes), 2)
        assert troca["consumo_medio_6m_depois"] == round(sum(depois) / len(depois), 2)
        assert troca["variacao_consumo_pct"] == round(((sum(depois) / len(depois)) / (sum(antes) / len(antes)) - 1) * 100, 2)
    assert repo._ucs["UC000008"]["medidor_trocado_recentemente"] is False
    assert repo.trocas_medidor_uc("UC000008") == []


def test_sqlite_filtra_uc_preserva_colunas_e_ordena_sem_recalcular_a6(cenario):
    with sqlite3.connect(cenario.path) as con:
        con.execute("UPDATE fato_troca_medidor SET consumo_medio_6m_antes = 123.45, consumo_medio_6m_depois = 100.01, variacao_consumo_pct = -18.99 WHERE id_uc = 'UC000001'")
        con.execute("INSERT INTO fato_troca_medidor SELECT id_uc, '2024-12', 'ANTERIOR', tipo_medidor_antigo, idade_medidor_antigo_anos, id_medidor_antigo, tipo_medidor_antigo, 0, NULL, NULL, classe, municipio, bairro FROM fato_troca_medidor WHERE id_uc = 'UC000001'")
    trocas = cenario.repo.trocas_medidor_uc(" uc000001 ")
    assert len(trocas) == 2
    assert {t["id_uc"] for t in trocas} == {"UC000001"}
    assert [t["mes_troca"] for t in trocas] == ["2025-09", "2024-12"]
    for t in trocas:
        assert TrocaMedidorUC.model_validate(t).model_dump() == t
    assert trocas[0]["consumo_medio_6m_antes"] == 123.45
    assert trocas[0]["consumo_medio_6m_depois"] == 100.01
    assert trocas[0]["variacao_consumo_pct"] == -18.99
    assert trocas[1]["consumo_medio_6m_antes"] == 0
    assert trocas[1]["consumo_medio_6m_depois"] is None
    assert trocas[1]["variacao_consumo_pct"] is None
    assert cenario.repo.trocas_medidor_uc("UC000001' OR 1=1 --") == []


@pytest.mark.parametrize(("atual", "referencia", "flag_atual", "flag_referencia"), [
    ("2025-09", "2025-08", True, False),
    ("2026-06", "2025-09", False, True),
    ("2026-06", "2026-05", False, False),
])
def test_consolidado_preserva_a6_e_flags_dos_meses_comparados(cenario, atual, referencia, flag_atual, flag_referencia):
    sqlite = visao_360(cenario.repo, "UC000001", atual, referencia)
    mock = visao_360(cenario.mock, "UC000001", atual, referencia)
    assert sqlite.model_dump(mode="json") == mock.model_dump(mode="json")
    assert sqlite.trocas_medidor[0].mes_troca == "2025-09"
    assert next(p for p in sqlite.consumo if p.competencia == "2025-09").troca_medidor is True
    assert sqlite.diagnostico_conta_alta.troca_medidor_atual is flag_atual
    assert sqlite.diagnostico_conta_alta.troca_medidor_referencia is flag_referencia
    sem_troca = visao_360(cenario.repo, "UC000008")
    assert sem_troca.trocas_medidor == []
    assert all(p.troca_medidor is False for p in sem_troca.consumo)


@pytest.mark.parametrize(("valor", "esperado"), [(0, False), (1, True), ("false", False), ("true", True), (None, None)])
def test_flags_a2_nao_dependem_do_cadastro_e_referencia_usa_mes_exato(cenario, valor, esperado):
    with sqlite3.connect(cenario.path) as con:
        con.execute("UPDATE fato_consumo_faturamento SET troca_medidor = ? WHERE id_uc = 'UC000008' AND mes_referencia = '2025-06'", (valor,))
    serie = cenario.repo.consumo_uc("UC000008")
    assert serie[-1]["troca_medidor"] is False
    assert serie[-1]["troca_medidor_ano_anterior"] is esperado
    assert serie[0]["troca_medidor_ano_anterior"] is None
    assert cenario.repo.trocas_medidor_uc("UC000008") == []
    diag = visao_360(cenario.repo, "UC000008", "2026-06", "2025-06").diagnostico_conta_alta
    assert diag.troca_medidor_referencia is esperado


def test_tabela_ausente_diferente_de_uc_sem_trocas_e_endpoint_completo(cenario):
    assert cenario.repo.trocas_medidor_uc("UC000008") == []
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            r = client.get("/api/unidades/UC000001/visao-360?competencia_atual=2025-09&competencia_referencia=2025-08")
            assert r.status_code == 200
            assert r.json() == visao_360(cenario.mock, "UC000001", "2025-09", "2025-08").model_dump(mode="json")
            with sqlite3.connect(cenario.path) as con:
                con.execute("DROP TABLE fato_troca_medidor")
            r = client.get("/api/unidades/UC000001/visao-360")
            assert r.status_code == 501 and "fato_troca_medidor" in r.json()["detail"]
            assert client.get("/api/unidades/UC999999/visao-360").status_code == 404
    finally:
        app.dependency_overrides.pop(repo_dep, None)
    with pytest.raises(NaoDisponivelNaGold, match="fato_troca_medidor"):
        cenario.repo.trocas_medidor_uc("UC000008")
