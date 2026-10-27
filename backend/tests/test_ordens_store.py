"""Armazém das ordens de inspeção: contrato comum (memória e SQLite) e garantias do SQLite."""
import threading

import pytest

from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.repositories.mock_repo import MockRepository
from app.repositories.ordens_store import MemoriaOrdensStore, SqliteOrdensStore

CAMPOS = {"id", "uc_id", "status", "motivo", "observacoes", "criada_em", "atualizada_em", "resultado"}


def _dados(uc="UC00001", motivo=None, observacoes=None):
    return {"uc_id": uc, "motivo": motivo, "observacoes": observacoes}


@pytest.fixture(params=["memoria", "sqlite"])
def store(request, tmp_path):
    """Roda cada teste de contrato nas duas implementações."""
    if request.param == "memoria":
        yield MemoriaOrdensStore()
    else:
        s = SqliteOrdensStore(str(tmp_path / "portal.db"))
        yield s
        s.close()


# ---------- contrato comum ----------
def test_criar_devolve_ordem_pendente_com_todos_os_campos(store):
    o = store.criar(_dados(motivo="queda de consumo"))
    assert set(o) == CAMPOS
    assert o["id"] == 1 and o["status"] == "PENDENTE" and o["resultado"] is None
    assert o["motivo"] == "queda de consumo" and o["criada_em"] == o["atualizada_em"]


def test_listar_filtra_por_status_e_mantem_ordem_de_criacao(store):
    a = store.criar(_dados("UC00001"))
    b = store.criar(_dados("UC00002"))
    store.atualizar(a["id"], {"status": "CANCELADA"})
    assert [o["id"] for o in store.listar()] == [a["id"], b["id"]]
    assert [o["id"] for o in store.listar("PENDENTE")] == [b["id"]]
    assert [o["id"] for o in store.listar("CANCELADA")] == [a["id"]]
    assert store.listar("CONCLUIDA") == []


def test_obter_inexistente_devolve_none(store):
    assert store.obter(999) is None


def test_atualizar_muda_status_e_guarda_resultado_com_acentos(store):
    o = store.criar(_dados())
    r = {"tipo": "ligacao_clandestina", "energia_recuperada_kwh": 120.5, "observacoes": "ligação clandestina no poste"}
    a = store.atualizar(o["id"], {"status": "CONCLUIDA", "resultado": r})
    assert a["status"] == "CONCLUIDA" and a["resultado"] == r
    assert store.obter(o["id"])["resultado"] == r
    assert a["criada_em"] == o["criada_em"]


def test_atualizar_ordem_inexistente_levanta_nao_encontrado(store):
    with pytest.raises(NaoEncontrado, match="999"):
        store.atualizar(999, {"status": "CANCELADA"})


# ---------- SQLite: persistência ----------
def test_ordens_sobrevivem_ao_reinicio(tmp_path):
    banco = str(tmp_path / "portal.db")
    s1 = SqliteOrdensStore(banco)
    o = s1.criar(_dados("UC00007", motivo="consumo caiu 40%", observacoes="vizinho relatou"))
    r = {"tipo": "fraude", "energia_recuperada_kwh": 80.0, "observacoes": None}
    s1.atualizar(o["id"], {"status": "CONCLUIDA", "resultado": r})
    s1.close()

    s2 = SqliteOrdensStore(banco)  # "reinício": nova conexão no mesmo arquivo
    [lida] = s2.listar()
    assert lida["uc_id"] == "UC00007" and lida["motivo"] == "consumo caiu 40%"
    assert lida["status"] == "CONCLUIDA" and lida["resultado"] == r
    s2.close()


def test_ids_continuam_de_onde_pararam_apos_reinicio(tmp_path):
    banco = str(tmp_path / "portal.db")
    s1 = SqliteOrdensStore(banco)
    s1.criar(_dados("UC00001"))
    s1.criar(_dados("UC00002"))
    s1.close()
    s2 = SqliteOrdensStore(banco)
    assert s2.criar(_dados("UC00003"))["id"] == 3
    s2.close()


def test_cria_a_pasta_do_banco_se_ela_nao_existir(tmp_path):
    banco = tmp_path / "ainda" / "nao" / "existe" / "portal.db"
    s = SqliteOrdensStore(str(banco))
    s.criar(_dados())
    s.close()
    assert banco.exists()


def test_mock_repository_guarda_as_ordens_no_armazem_recebido(tmp_path):
    banco = str(tmp_path / "portal.db")
    s1 = SqliteOrdensStore(banco)
    repo1 = MockRepository(ordens=s1)
    o = repo1.criar_ordem(_dados("UC00001"))
    repo1.atualizar_ordem(o["id"], {"status": "EM_CAMPO"})
    s1.close()

    s2 = SqliteOrdensStore(banco)
    repo2 = MockRepository(ordens=s2)
    assert repo2.obter_ordem(o["id"])["status"] == "EM_CAMPO"
    assert [x["id"] for x in repo2.listar_ordens("EM_CAMPO")] == [o["id"]]
    s2.close()


def test_mock_repository_sem_armazem_continua_em_memoria():
    repo = MockRepository()
    o = repo.criar_ordem(_dados())
    assert repo.obter_ordem(o["id"])["status"] == "PENDENTE"


# ---------- SQLite: garantias do banco ----------
def test_indice_impede_duas_ordens_ativas_na_mesma_uc(tmp_path):
    s = SqliteOrdensStore(str(tmp_path / "portal.db"))
    a = s.criar(_dados("UC00001"))
    with pytest.raises(ConflitoDeEstado, match="ativa"):
        s.criar(_dados("UC00001"))
    s.atualizar(a["id"], {"status": "EM_CAMPO"})  # EM_CAMPO também conta como ativa
    with pytest.raises(ConflitoDeEstado):
        s.criar(_dados("UC00001"))
    s.atualizar(a["id"], {"status": "CANCELADA"})
    assert s.criar(_dados("UC00001"))["id"] == 2  # liberada: pode abrir outra
    s.close()


def test_nao_reabre_ordem_antiga_se_ja_existe_outra_ativa(tmp_path):
    s = SqliteOrdensStore(str(tmp_path / "portal.db"))
    antiga = s.criar(_dados("UC00001"))
    s.atualizar(antiga["id"], {"status": "CANCELADA"})
    s.criar(_dados("UC00001"))
    with pytest.raises(ConflitoDeEstado):
        s.atualizar(antiga["id"], {"status": "PENDENTE"})
    assert s.obter(antiga["id"])["status"] == "CANCELADA"
    s.close()


def test_status_invalido_e_campo_desconhecido_sao_rejeitados(tmp_path):
    s = SqliteOrdensStore(str(tmp_path / "portal.db"))
    o = s.criar(_dados())
    with pytest.raises(ValueError, match="inválidos"):
        s.atualizar(o["id"], {"status": "TALVEZ"})
    with pytest.raises(ValueError, match="uc_id"):
        s.atualizar(o["id"], {"uc_id": "UC99999"})
    assert s.obter(o["id"])["status"] == "PENDENTE" and s.obter(o["id"])["uc_id"] == "UC00001"
    s.close()


def test_requisicoes_simultaneas_na_mesma_uc_criam_uma_so_ordem(tmp_path):
    s = SqliteOrdensStore(str(tmp_path / "portal.db"))
    resultados, trava = [], threading.Barrier(8)

    def tenta():
        trava.wait()
        try:
            resultados.append(("ok", s.criar(_dados("UC00001"))["id"]))
        except ConflitoDeEstado:
            resultados.append(("conflito", None))

    threads = [threading.Thread(target=tenta) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(r[0] for r in resultados) == ["conflito"] * 7 + ["ok"]
    assert len(s.listar()) == 1
    s.close()


def test_criacoes_simultaneas_em_ucs_diferentes_nao_repetem_id(tmp_path):
    s = SqliteOrdensStore(str(tmp_path / "portal.db"))
    ids, trava = [], threading.Barrier(8)

    def cria(i):
        trava.wait()
        ids.append(s.criar(_dados(f"UC{i:05d}"))["id"])

    threads = [threading.Thread(target=cria, args=(i,)) for i in range(1, 9)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(ids) == list(range(1, 9))
    s.close()
