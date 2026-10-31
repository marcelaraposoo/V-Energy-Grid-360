"""B1 e Visão 360 com SQLite fictício, sem substituir os métodos do repositório."""
from datetime import datetime, timedelta
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NaoDisponivelNaGold
from app.main import app
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.schemas import AtendimentoUC
from app.services.unidades import visao_360
from tests.gold_fixture import criar_gold_db


@pytest.fixture
def cenario(tmp_path):
    mock = MockRepository()
    uc, outra = mock.d["dim_uc"][:2]
    datas = ["2022-07-01T12:34:56", "2025-06-30T23:59:59", "2025-07-01T00:00:00",
             "2026-01-01T00:00:00", "2026-06-30T18:35:12"]
    chamados = [{
        "protocolo": f"AT{i:09d}", "id_uc": uc["id_uc"],
        "municipio": uc["municipio"], "bairro": uc["bairro"], "classe": uc["classe"],
        "canal": "APP", "assunto": "FATURA", "subassunto": "VALOR ALTO",
        "data_hora_abertura": data,
        "data_hora_fechamento": (datetime.fromisoformat(data) + timedelta(hours=1)).isoformat(),
        "mes_referencia": data[:7], "aberto": False, "tempo_resolucao_horas": 1,
        "qtd_tratativas": 2, "ultima_acao": "ABERTURA", "nota_satisfacao": None if i % 2 else 4.1,
    } for i, data in enumerate(datas, 1)]
    chamados.append({**chamados[-1], "protocolo": "AT999999999", "id_uc": outra["id_uc"],
                     "municipio": outra["municipio"], "bairro": outra["bairro"], "classe": outra["classe"]})
    mock.d = {**mock.d, "fato_atendimento": chamados}
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        for tabela in ("fato_consumo_faturamento", "fato_interrupcao", "dec_fec_alimentador_mensal", "fato_atendimento"):
            linhas = mock.d[tabela]
            colunas = list(linhas[0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                            [[r[c] for c in colunas] for r in reversed(linhas)])
    return SimpleNamespace(repo=SqliteRepository(path), mock=mock, path=path, uc_id=uc["id_uc"])


def test_b1_filtra_uc_ordena_e_preserva_horarios_notas_nulas_e_ultima_acao(cenario):
    dados = cenario.repo.atendimentos_uc(cenario.uc_id.lower())
    assert dados == sorted(cenario.mock.atendimentos_uc(cenario.uc_id), key=lambda a: a["data"], reverse=True)
    assert len(dados) == 5
    assert {a["uc_id"] for a in dados} == {cenario.uc_id}
    assert dados[0]["data"] == "2026-06-30T18:35:12"
    assert dados[0]["data_fechamento"] == "2026-06-30T19:35:12"
    assert dados[0]["nota_satisfacao"] is None
    assert dados[1]["nota_satisfacao"] == 4.1
    for a in dados:
        assert a["aberto"] is False and a["ultima_acao"] == "ABERTURA"
        assert AtendimentoUC.model_validate(a).model_dump(mode="json") == a
        assert "tratativas" not in a and "status" not in a


@pytest.mark.parametrize(("valor", "esperado"), [(0, False), (1, True), ("false", False), ("true", True)])
def test_situacao_vem_da_flag_e_nao_da_ultima_acao(cenario, valor, esperado):
    with sqlite3.connect(cenario.path) as con:
        con.execute("""UPDATE fato_atendimento SET aberto = ?, ultima_acao = 'ENCERRAMENTO',
                       data_hora_fechamento = ?, tempo_resolucao_horas = ?
                       WHERE protocolo = 'AT000000005'""",
                    (valor, None if esperado else "2026-06-30T19:35:12", None if esperado else 1))
    atendimento = AtendimentoUC.model_validate(cenario.repo.atendimentos_uc(cenario.uc_id)[0])
    assert atendimento.aberto is esperado
    assert (atendimento.data_fechamento is None) is esperado
    assert (atendimento.tempo_resolucao_horas is None) is esperado


@pytest.mark.parametrize(("periodo", "inicio", "protocolos"), [
    ("6_meses", "2026-01", ["AT000000005", "AT000000004"]),
    ("12_meses", "2025-07", ["AT000000005", "AT000000004", "AT000000003"]),
    ("todos", "2022-07", ["AT000000005", "AT000000004", "AT000000003", "AT000000002", "AT000000001"]),
])
def test_consolidado_filtra_por_abertura_sem_alterar_outros_blocos(cenario, periodo, inicio, protocolos):
    padrao = visao_360(cenario.repo, cenario.uc_id)
    dados = visao_360(cenario.repo, cenario.uc_id, periodo_atendimentos=periodo)
    esperado = visao_360(cenario.mock, cenario.uc_id, periodo_atendimentos=periodo)
    assert dados.model_dump(mode="json") == esperado.model_dump(mode="json")
    assert [a.protocolo for a in dados.atendimentos] == protocolos
    assert dados.periodo_atendimentos.periodo_inicio == inicio
    assert dados.periodo_atendimentos.periodo_fim == "2026-06"
    excluir = {"atendimentos", "periodo_atendimentos"}
    assert dados.model_dump(exclude=excluir) == padrao.model_dump(exclude=excluir)


def test_sem_chamados_e_tabela_ausente_sao_situacoes_distintas(cenario):
    assert cenario.repo.atendimentos_uc("UC000003") == []
    assert cenario.repo.atendimentos_uc("UC999999") == []
    assert visao_360(cenario.repo, "UC000003").atendimentos == []
    with sqlite3.connect(cenario.path) as con:
        con.execute("DROP TABLE fato_atendimento")
    with pytest.raises(NaoDisponivelNaGold, match="fato_atendimento"):
        cenario.repo.atendimentos_uc(cenario.uc_id)


def test_endpoint_completo_sqlite_sem_isolar_blocos(cenario):
    app.dependency_overrides[repo_dep] = lambda: cenario.repo
    try:
        with TestClient(app) as client:
            for periodo in ("6_meses", "12_meses", "todos"):
                resposta = client.get(f"/api/unidades/{cenario.uc_id}/visao-360", params={"periodo_atendimentos": periodo})
                assert resposta.status_code == 200
                esperado = visao_360(cenario.mock, cenario.uc_id, periodo_atendimentos=periodo).model_dump(mode="json")
                assert resposta.json() == esperado
            assert client.get("/api/unidades/UC999999/visao-360").status_code == 404
    finally:
        app.dependency_overrides.pop(repo_dep, None)
