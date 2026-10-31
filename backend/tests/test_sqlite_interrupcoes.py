"""A7/A8 no SQLite: períodos, separação UC/alimentador e contexto dos indicadores."""
from datetime import datetime, timedelta
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoDisponivelNaGold
from app.main import app
from app.mock.mock_data import build_dec_fec_alimentador_mensal
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.services.unidades import visao_360
from tests.gold_fixture import criar_gold_db


@pytest.fixture
def cenario(tmp_path):
    mock = MockRepository()
    meses = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 7)]
    ucs = [{**u, "alimentador": "AL1" if i < 3 else "AL2", "municipio": "Recife" if i < 3 else "Olinda",
            "data_ligacao": "2026-01-01" if i == 1 else "2024-01-01",
            "primeiro_mes_leitura": "2026-01" if i == 1 else meses[0], "ultimo_mes_leitura": meses[-1]}
           for i, u in enumerate(mock.d["dim_uc"][:4])]
    alimentadores = [{"id": "AL1", "municipio": "Recife", "ucs_total": 3},
                    {"id": "AL2", "municipio": "Olinda", "ucs_total": 1}]
    eventos = []
    for uc, data, minutos, causa in [
        (ucs[0], "2024-12-31T22:00:00", 60, None),
        (ucs[0], "2025-01-01T00:00:00", 60, None),
        (ucs[0], "2025-07-01T00:00:00", 60, None),
        (ucs[0], "2026-01-01T23:35:12", 90, None),
        (ucs[1], "2026-01-02T12:00:00", 30, "VEGETACAO"),
        (ucs[3], "2026-01-02T12:00:00", 120, "CLIMATICA"),
        (ucs[0], "2026-06-30T22:00:00", 30, None),
        (ucs[0], "2026-07-01T00:00:00", 60, None),
    ]:
        eventos.append({
            "id_ocorrencia": f"OC{len(eventos):06d}", "id_uc": uc["id_uc"],
            "alimentador": uc["alimentador"], "municipio": uc["municipio"],
            "bairro": uc["bairro"], "classe": uc["classe"], "tipo": "FALTA DE ENERGIA",
            "causa": causa, "causa_evitavel": causa == "VEGETACAO",
            "data_hora_inicio": data,
            "data_hora_fim": (datetime.fromisoformat(data) + timedelta(minutes=minutos)).isoformat(),
            "mes_referencia": data[:7], "duracao_min": minutos,
        })
    mensais = build_dec_fec_alimentador_mensal(ucs, eventos, alimentadores, meses)
    # Na exportação real os acumulados de 12 meses ainda são nulos no início da base.
    for r in mensais:
        if r["mes_referencia"] < "2025-12":
            r.update(dec_12m_horas=None, fec_12m=None)
    por_id = {u["id_uc"]: u for u in ucs}
    faturas = [f for f in mock.d["fato_consumo_faturamento"]
               if f["id_uc"] in por_id and por_id[f["id_uc"]]["primeiro_mes_leitura"] <= f["mes_referencia"] <= meses[-1]]
    mock.d = {**mock.d, "dim_uc": ucs, "alimentadores": alimentadores, "competencias": meses,
              "fato_interrupcao": eventos, "dec_fec_alimentador_mensal": mensais,
              "fato_consumo_faturamento": faturas}
    mock._ucs = por_id
    mock._faturas_por_uc = {u["id_uc"]: [f for f in faturas if f["id_uc"] == u["id_uc"]] for u in ucs}
    path = criar_gold_db(tmp_path / "gold.db", ucs=ucs)
    with sqlite3.connect(path) as con:
        for tabela in ("fato_interrupcao", "dec_fec_alimentador_mensal", "fato_consumo_faturamento"):
            linhas = mock.d[tabela]
            colunas = list(linhas[0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                            [[r[c] for c in colunas] for r in reversed(linhas)])
    return SimpleNamespace(repo=SqliteRepository(path), mock=mock, path=path, ucs=ucs)


def test_ocorrencias_filtram_uc_alimentador_municipio_e_limites(cenario):
    repo = cenario.repo
    uc = cenario.ucs[0]["id_uc"]
    registros = repo.ocorrencias("2025-07", "2026-06", alimentador_id="al1", municipio="Recife", uc_id=uc.lower())
    assert len(registros) == 3
    assert {r["uc_id"] for r in registros} == {uc}
    assert registros[0]["data"] == "2025-07-01T00:00:00"
    assert registros[-1]["data"] == "2026-06-30T22:00:00"
    assert registros[1]["data_fim"] == "2026-01-02T01:05:12"
    assert all(r["causa"] is None and r["causa_evitavel"] is False for r in registros)
    esperado = cenario.mock.ocorrencias("2025-07", "2026-06", uc_id=uc)
    assert registros == sorted(esperado, key=lambda r: (r["data"], r["ocorrencia_id"]))
    assert repo.ocorrencias("2025-07", "2026-06", alimentador_id="AL2", uc_id=uc) == []
    assert repo.ocorrencias("2025-07", "2026-06", municipio="Olinda", uc_id=uc) == []


def test_grade_mensal_preserva_zeros_nulos_e_denominadores_da_gold(cenario):
    linhas = cenario.repo.indicadores_continuidade("2025-01", "2026-06", alimentador_id="al1", municipio="Recife")
    assert linhas == cenario.mock.indicadores_continuidade("2025-01", "2026-06", alimentador_id="AL1", municipio="Recife")
    assert len(linhas) == 18
    assert linhas[0]["qtd_ucs_alimentador_mes"] == 2
    assert linhas[-1]["qtd_ucs_alimentador_mes"] == 3
    assert linhas[0]["dec_12m_horas"] is None
    fevereiro = next(r for r in linhas if r["mes_referencia"] == "2026-02")
    assert fevereiro["dec_horas"] == fevereiro["fec"] == fevereiro["horas_interrompidas"] == 0
    assert cenario.repo.indicadores_continuidade("2025-01", "2026-06", alimentador_id="AL1", municipio="Olinda") == []
    assert cenario.repo.indicadores_continuidade("2030-01", "2030-12", alimentador_id="AL1") == []


@pytest.mark.parametrize(("periodo", "inicio", "quantidade", "minutos", "impacto", "dec", "fec"), [
    ("6_meses", "2026-01", 2, 120, 2.5, 5 / 6, 1),
    ("12_meses", "2025-07", 3, 180, 3.5, 4 / 3, 1.5),
    ("todos", "2025-01", 4, 240, 4.5, 11 / 6, 2),
])
def test_visao_360_contexto_do_alimentador_nao_se_confunde_com_a_uc(
    cenario, monkeypatch, periodo, inicio, quantidade, minutos, impacto, dec, fec,
):
    # Único bloco isolado: B1/atendimentos será integrado na próxima etapa.
    monkeypatch.setattr(cenario.repo, "atendimentos_uc", lambda _: [])
    uc = cenario.ucs[0]["id_uc"]
    resposta = visao_360(cenario.repo, uc, periodo_interrupcoes=periodo).interrupcoes
    assert resposta.periodo_inicio == inicio and resposta.periodo_fim == "2026-06"
    assert resposta.qtd_ocorrencias == len(resposta.historico) == quantidade
    assert resposta.duracao_total_min == minutos
    assert {o.uc_id for o in resposta.historico} == {uc}
    assert resposta.dec_horas == pytest.approx(dec, abs=1e-6)
    assert resposta.fec_vezes == pytest.approx(fec, abs=1e-6)
    assert resposta.horas_interrompidas == impacto
    assert resposta.qtd_ucs_alimentador_mes == 3
    assert resposta.competencia_base_ucs == "2026-06"
    assert resposta.historico[0].data.isoformat() == "2026-06-30T22:00:00"


def test_uc_sem_eventos_mantem_contexto_do_alimentador(cenario, monkeypatch):
    monkeypatch.setattr(cenario.repo, "atendimentos_uc", lambda _: [])
    dados = visao_360(cenario.repo, cenario.ucs[2]["id_uc"]).interrupcoes
    assert dados.historico == [] and dados.qtd_ocorrencias == 0 and dados.duracao_total_min == 0
    assert dados.horas_interrompidas == 3.5
    assert dados.dec_horas > 0 and dados.qtd_ucs_alimentador_mes == 3


def test_sem_indicadores_nao_apresenta_zero_falso(cenario, monkeypatch):
    with sqlite3.connect(cenario.path) as con:
        con.execute("DELETE FROM dec_fec_alimentador_mensal")
    monkeypatch.setattr(cenario.repo, "atendimentos_uc", lambda _: [])
    dados = visao_360(cenario.repo, cenario.ucs[0]["id_uc"]).interrupcoes
    assert dados.qtd_ocorrencias == 3
    assert dados.dec_horas is dados.fec_vezes is dados.horas_interrompidas is None
    assert dados.qtd_ucs_alimentador_mes is dados.competencia_base_ucs is None


@pytest.mark.parametrize(("tabela", "metodo"), [("fato_interrupcao", "ocorrencias"), ("dec_fec_alimentador_mensal", "indicadores_continuidade")])
def test_tabela_ausente_informa_indisponibilidade(cenario, tabela, metodo):
    with sqlite3.connect(cenario.path) as con:
        con.execute(f"DROP TABLE {tabela}")
    with pytest.raises(NaoDisponivelNaGold, match=tabela):
        getattr(cenario.repo, metodo)("2025-01", "2026-06")


def test_endpoint_entrega_rede_e_contexto_com_b1_isolada(cenario, monkeypatch):
    monkeypatch.setattr(cenario.repo, "atendimentos_uc", lambda _: [])
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            r = client.get(f"/api/unidades/{cenario.ucs[0]['id_uc']}/visao-360", params={"periodo_interrupcoes": "6_meses"})
            assert r.status_code == 200
            dados = r.json()["interrupcoes"]
            assert dados["horas_interrompidas"] == 2.5
            assert dados["qtd_ucs_alimentador_mes"] == 3
            assert dados["competencia_base_ucs"] == "2026-06"
            assert dados["historico"][-1]["data"] == "2026-01-01T23:35:12"
    finally:
        app.dependency_overrides.pop(repo_dep, None)


def test_endpoint_ainda_informa_atendimentos_pendentes(cenario):
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            r = client.get(f"/api/unidades/{cenario.ucs[0]['id_uc']}/visao-360")
            assert r.status_code == 501 and "fato_atendimento" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(repo_dep, None)
