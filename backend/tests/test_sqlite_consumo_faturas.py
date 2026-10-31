"""Leitura da A2 no SQLite e uso no diagnóstico, com uma Gold inteiramente fictícia."""
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoDisponivelNaGold
from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.schemas import FaturaUC
from app.services.unidades import visao_360
from tests.gold_fixture import criar_gold_db


@pytest.fixture(scope="module")
def mock():
    return MockRepository()


@pytest.fixture
def cenario(mock, tmp_path):
    ucs = mock.d["dim_uc"][:3]
    ids = {u["id_uc"] for u in ucs[:2]}
    linhas = [f for f in mock.d["fato_consumo_faturamento"] if f["id_uc"] in ids]
    path = criar_gold_db(tmp_path / "gold.db", ucs=ucs)
    colunas = list(linhas[0])
    with sqlite3.connect(path) as con:
        con.execute(f"CREATE TABLE fato_consumo_faturamento ({', '.join(colunas)})")
        con.executemany(f"INSERT INTO fato_consumo_faturamento VALUES ({', '.join('?' for _ in colunas)})",
                        [[f[c] for c in colunas] for f in reversed(linhas)])
    return SimpleNamespace(repo=SqliteRepository(path), path=path, uc_id=ucs[0]["id_uc"], sem_historico=ucs[2]["id_uc"])


def isolar_demais_blocos(repo, monkeypatch):
    """Somente no teste: isola os outros blocos para validar a leitura da A2."""
    monkeypatch.setattr(repo, "ocorrencias", lambda *args, **kwargs: [])
    monkeypatch.setattr(repo, "indicadores_continuidade", lambda *args, **kwargs: [])
    monkeypatch.setattr(repo, "atendimentos_uc", lambda *args, **kwargs: [])


def test_leitura_filtra_uc_ordena_competencias_e_preserva_os_valores_da_gold(cenario, mock):
    repo, uc = cenario.repo, cenario.uc_id
    serie = repo.consumo_uc(uc.lower())
    faturas = repo.faturas_uc(uc.lower())
    assert serie == mock.consumo_uc(uc)
    assert faturas == mock.faturas_uc(uc)
    assert len(serie) == len(faturas) == 48
    assert [p["competencia"] for p in serie] == sorted(p["competencia"] for p in serie)
    assert {f["uc_id"] for f in faturas} == {uc}
    originais = {f["mes_referencia"]: f for f in mock.d["fato_consumo_faturamento"] if f["id_uc"] == uc}
    for ponto in serie:
        original = originais[ponto["competencia"]]
        for campo in ("consumo_kwh", "consumo_kwh_ano_anterior", "variacao_consumo_ano_anterior_pct", "valor_total"):
            assert ponto[campo] == original[campo]
    for ponto in serie[:12]:
        assert ponto["consumo_kwh_ano_anterior"] is None
        assert ponto["variacao_consumo_ano_anterior_pct"] is None
        assert ponto["valor_total_ano_anterior"] is None


def test_faturas_preservam_tributos_preco_e_situacao_sem_aplicar_regras_do_mock(cenario):
    with sqlite3.connect(cenario.path) as con:
        con.execute("""UPDATE fato_consumo_faturamento SET tributos = 17.83, preco_medio_kwh = 0.987654,
                       status_fatura = 'PAGA', dias_atraso = 25, data_pagamento = '2026-06-30'
                       WHERE id_uc = ? AND mes_referencia = '2026-06'""", (cenario.uc_id,))
    fatura = FaturaUC.model_validate(cenario.repo.faturas_uc(cenario.uc_id)[-1])
    assert fatura.tributos == 17.83
    assert fatura.preco_medio_kwh == 0.987654
    assert fatura.status == "paga"
    assert fatura.data_pagamento.isoformat() == "2026-06-30"


def test_valor_do_ano_anterior_usa_mes_exato_mesmo_com_lacunas(cenario):
    with sqlite3.connect(cenario.path) as con:
        con.execute("DELETE FROM fato_consumo_faturamento WHERE id_uc = ? AND mes_referencia = '2025-03'", (cenario.uc_id,))
        esperado = con.execute("SELECT valor_total FROM fato_consumo_faturamento WHERE id_uc = ? AND mes_referencia = '2025-06'", (cenario.uc_id,)).fetchone()[0]
    atual = cenario.repo.consumo_uc(cenario.uc_id)[-1]
    assert atual["competencia"] == "2026-06"
    assert atual["valor_total_ano_anterior"] == esperado
    with sqlite3.connect(cenario.path) as con:
        con.execute("DELETE FROM fato_consumo_faturamento WHERE id_uc = ? AND mes_referencia = '2025-06'", (cenario.uc_id,))
    assert cenario.repo.consumo_uc(cenario.uc_id)[-1]["valor_total_ano_anterior"] is None


@pytest.mark.parametrize(("atual", "referencia"), [
    (None, None), ("2023-06", "2022-07"), ("2026-06", "2025-06"),
])
def test_diagnostico_historico_e_ultima_fatura_equivalem_ao_mock(cenario, mock, monkeypatch, atual, referencia):
    isolar_demais_blocos(cenario.repo, monkeypatch)
    resposta = visao_360(cenario.repo, cenario.uc_id, atual, referencia)
    esperado = visao_360(mock, cenario.uc_id, atual, referencia)
    for campo in ("consumo", "faturas", "resumo_faturas", "diagnostico_conta_alta"):
        assert getattr(resposta, campo) == getattr(esperado, campo)
    assert len(resposta.consumo) == 12 and len(resposta.faturas) == 1
    assert resposta.faturas[0].competencia == "2026-06"


@pytest.mark.parametrize(("campo", "valor"), [("consumo_kwh", 0), ("valor_total", 0), ("valor_total", None)])
def test_diagnostico_referencia_zero_ou_nula_nao_produz_percentual_invalido(cenario, monkeypatch, campo, valor):
    with sqlite3.connect(cenario.path) as con:
        con.execute(f"UPDATE fato_consumo_faturamento SET {campo} = ? WHERE id_uc = ? AND mes_referencia = '2026-05'", (valor, cenario.uc_id))
    isolar_demais_blocos(cenario.repo, monkeypatch)
    diag = visao_360(cenario.repo, cenario.uc_id).diagnostico_conta_alta
    metrica = diag.consumo if campo == "consumo_kwh" else diag.faturamento
    assert metrica.valor_referencia == valor
    assert metrica.variacao_pct is None
    assert metrica.classificacao is None


def test_uc_sem_registros_nao_e_confundida_com_tabela_ausente(cenario, tmp_path, mock):
    for uc in (cenario.sem_historico, "UC999999"):
        assert cenario.repo.consumo_uc(uc) == []
        assert cenario.repo.faturas_uc(uc) == []
    sem_fato = SqliteRepository(criar_gold_db(tmp_path / "sem-fato.db", ucs=mock.d["dim_uc"][:1]))
    for metodo in (sem_fato.consumo_uc, sem_fato.faturas_uc):
        with pytest.raises(NaoDisponivelNaGold, match="fato_consumo_faturamento"):
            metodo(cenario.uc_id)


def test_endpoint_consolidado_usa_a2_sem_mudar_o_contrato(cenario, monkeypatch):
    isolar_demais_blocos(cenario.repo, monkeypatch)
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            r = client.get(f"/api/unidades/{cenario.uc_id}/visao-360")
            assert r.status_code == 200
            dados = r.json()
            assert len(dados["consumo"]) == 12
            assert dados["faturas"][0]["competencia"] == "2026-06"
            assert dados["diagnostico_conta_alta"]["competencia_referencia"] == "2026-05"
            pagina = client.get(f"/api/unidades/{cenario.uc_id}/faturas", params={"aba": "historico"}).json()
            assert pagina["total"] == 48 and len(pagina["itens"]) == 10
            assert dados["resumo_faturas"] == pagina["resumo"]
    finally:
        app.dependency_overrides.pop(repo_dep, None)


def test_endpoint_informa_tabela_de_rede_ausente(cenario):
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            r = client.get(f"/api/unidades/{cenario.uc_id}/visao-360")
            assert r.status_code == 501
            assert "fato_interrupcao" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(repo_dep, None)
