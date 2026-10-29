"""Fila de suspeitas vinda da Gold (`fila_inspecao`): leitura no SQLite, ordem da Gold e insights da tela de perdas."""
import sqlite3

import pytest

from app.core.errors import NaoDisponivelNaGold
from app.repositories.sqlite_repo import SqliteRepository
from app.services import perdas
from tests.gold_fixture import criar_gold_db

LINHAS = [
    # id_uc, prioridade, score, motivo, kwh_estimado_recuperar_mes
    ("UC00002", 2, 71.5, "consumo caiu 40%; medidor eletromecânico com 22 anos", 120.0),
    ("UC00001", 1, 88.0, "consumo caiu 60% vs. 12 meses anteriores", "310,5"),
    ("UC00003", 3, None, "sem score", 10),  # descartada: sem score não dá para priorizar
    (None, 4, 50, "sem UC", 10),  # descartada
    ("UC00004", 5, 130, "score acima de 100", -5),  # score vira 1,0 e energia negativa vira 0
]


@pytest.fixture
def gold(tmp_path):
    caminho = criar_gold_db(tmp_path / "gold.db")
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE fila_inspecao (id_uc, prioridade, score, motivo, kwh_estimado_recuperar_mes)")
    con.executemany("INSERT INTO fila_inspecao VALUES (?,?,?,?,?)", LINHAS)
    con.commit()
    con.close()
    return caminho


def test_sem_a_tabela_da_gold_a_fila_continua_indisponivel(tmp_path):
    repo = SqliteRepository(criar_gold_db(tmp_path / "gold.db"))
    with pytest.raises(NaoDisponivelNaGold, match="fila_inspecao"):
        repo.suspeitas()


def test_suspeitas_le_a_gold_e_descarta_linhas_inutilizaveis(gold):
    por_uc = {s["uc_id"]: s for s in SqliteRepository(gold).suspeitas()}
    assert set(por_uc) == {"UC00001", "UC00002", "UC00004"}
    primeira = por_uc["UC00001"]
    assert primeira["prioridade"] == 1 and primeira["score"] == 88.0
    assert primeira["energia_recuperavel_kwh_mes"] == 310.5  # vírgula decimal aceita
    assert primeira["probabilidade"] == pytest.approx(0.88)


def test_motivo_da_gold_vira_lista(gold):
    por_uc = {s["uc_id"]: s for s in SqliteRepository(gold).suspeitas()}
    assert por_uc["UC00002"]["motivos"] == ["consumo caiu 40%", "medidor eletromecânico com 22 anos"]


def test_valores_fora_da_faixa_sao_limitados(gold):
    extremo = {s["uc_id"]: s for s in SqliteRepository(gold).suspeitas()}["UC00004"]
    assert extremo["probabilidade"] == 1.0
    assert extremo["energia_recuperavel_kwh_mes"] == 0.0


class RepoFalso:
    UCS = {c: {"uc_id": c, "titular": c, "municipio": m, "bairro": "B", "classe": "B1"}
           for c, m in (("A", "OLINDA"), ("B", "RECIFE"), ("C", "RECIFE"))}

    def __init__(self, suspeitas, ordens=()):
        self._s, self._o = suspeitas, list(ordens)

    def suspeitas(self):
        return self._s

    def uc(self, uc_id):
        return self.UCS.get(uc_id)

    def listar_ordens(self, status=None):
        return self._o


def _s(uc, prob, kwh, **extra):
    return {"uc_id": uc, "motivos": ["m"], "probabilidade": prob, "energia_recuperavel_kwh_mes": kwh, **extra}


def test_sem_prioridade_da_gold_vale_probabilidade_vezes_energia():
    itens, total = perdas.fila(RepoFalso([_s("A", 0.5, 100), _s("B", 0.9, 100), _s("C", 0.9, 100)]))
    assert [i.uc_id for i in itens] == ["B", "C", "A"] and total == 3  # empate mantém a ordem de origem
    assert itens[0].prioridade_score == 90.0


def test_com_prioridade_da_gold_a_ordem_da_gold_manda():
    repo = RepoFalso([
        _s("B", 0.99, 1000, score=60.0, prioridade=2),
        _s("A", 0.10, 5, score=80.0, prioridade=1),
        _s("Z", 0.90, 5, score=99.0, prioridade=0),  # UC fora do cadastro: ignorada
    ])
    itens, total = perdas.fila(repo)
    assert [i.uc_id for i in itens] == ["A", "B"] and total == 2
    assert itens[0].prioridade_score == 80.0  # mostra o score da Gold


def test_uc_com_ordem_ativa_sai_da_fila_da_gold():
    repo = RepoFalso([_s("A", 0.5, 1, score=80.0, prioridade=1), _s("B", 0.5, 1, score=70.0, prioridade=2)],
                     ordens=[{"uc_id": "A", "status": "PENDENTE"}])
    itens, _ = perdas.fila(repo)
    assert [(i.uc_id, i.posicao) for i in itens] == [("B", 1)]


def test_insights_da_fila_resumem_cobertura_e_concentracao():
    repo = RepoFalso([_s("A", 0.5, 1000), _s("B", 0.5, 3000), _s("C", 0.5, 6000)])
    destaque, concentracao = perdas.insights_fila(repo)
    assert destaque.tipo == "destaque" and "3 unidades suspeitas" in destaque.texto
    assert "10.000 kWh/mês" in destaque.texto and "100%" in destaque.texto
    assert destaque.dados["cobertura_pct"] == 100.0
    assert "RECIFE concentra 2 das 3" in concentracao.texto


def test_insights_da_fila_vazia():
    assert perdas.insights_fila(RepoFalso([])) == []


def test_api_insights_de_perdas_traz_o_resumo_da_fila():
    from fastapi.testclient import TestClient

    from app.main import app

    insights = TestClient(app).get("/api/ia/insights?tela=perdas").json()
    assert insights and insights[0]["tipo"] == "destaque"
