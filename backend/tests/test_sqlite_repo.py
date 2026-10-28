"""SqliteRepository (etapa 1): o que sai da dim_uc, o que ainda não existe na Gold e as garantias de leitura."""
import sqlite3

import pytest

from app.core.errors import NaoDisponivelNaGold
from app.repositories.ordens_store import MemoriaOrdensStore
from app.repositories.sqlite_repo import SqliteRepository
from tests.gold_fixture import COLUNAS, criar_gold_db


@pytest.fixture
def repo(tmp_path):
    return SqliteRepository(criar_gold_db(tmp_path / "gold.db"), ordens=MemoriaOrdensStore())


# ---------- abertura do banco ----------
def test_arquivo_inexistente_explica_como_resolver(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        SqliteRepository(str(tmp_path / "nao_existe.db"))
    assert "DATA_SOURCE=mock" in str(e.value)


def test_banco_sem_a_tabela_dim_uc(tmp_path):
    caminho = tmp_path / "vazio.db"
    sqlite3.connect(str(caminho)).close()
    with pytest.raises(RuntimeError) as e:
        SqliteRepository(str(caminho))
    assert "dim_uc" in str(e.value)


def test_dim_uc_sem_coluna_obrigatoria(tmp_path):
    colunas = [c for c in COLUNAS if c != "alimentador"]
    with pytest.raises(RuntimeError) as e:
        SqliteRepository(criar_gold_db(tmp_path / "g.db", colunas=colunas))
    assert "alimentador" in str(e.value)


def test_funciona_em_pasta_com_espaco_no_nome(tmp_path):
    pasta = tmp_path / "Case - DEV"
    pasta.mkdir()
    assert SqliteRepository(criar_gold_db(pasta / "gold.db")).uc("UC00001") is not None


def test_conexao_e_somente_leitura(repo):
    con = repo._conectar()
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM dim_uc")
    finally:
        con.close()


def test_colunas_opcionais_ausentes_viram_none(tmp_path):
    opcionais = {"variacao_consumo_12m_pct", "consumo_medio_12m_kwh", "documento_mascarado", "possui_gd"}
    r = SqliteRepository(criar_gold_db(tmp_path / "g.db", colunas=[c for c in COLUNAS if c not in opcionais]))
    uc = r.uc("UC00001")
    assert uc["variacao_consumo_12m_pct"] is None and uc["documento_mascarado"] is None
    assert r.gd_uc("UC00001") is None


# ---------- catálogos ----------
def test_municipios_bairros_usa_o_par_municipio_bairro(repo):
    assert repo.municipios_bairros() == {
        "OLINDA": ["CENTRO"], "PAULISTA": ["JANGA"], "RECIFE": ["BOA VIAGEM", "CENTRO"],
    }


def test_classes_sao_as_da_gold_com_descricao(repo):
    assert repo.classes() == {
        "COMERCIAL": "Comercial", "INDUSTRIAL": "Industrial", "PODER PUBLICO": "Poder público",
        "RESIDENCIAL": "Residencial", "RURAL": "Rural",
    }


def test_alimentadores_contam_ucs_e_resolvem_municipio_principal(repo):
    alims = {a["id"]: a for a in repo.alimentadores()}
    assert alims["AL001"] == {"id": "AL001", "municipio": "RECIFE", "ucs_total": 2}
    # AL002 atende OLINDA (2 UCs) e PAULISTA (1): conta as 3 e fica com o município de mais UCs
    assert alims["AL002"] == {"id": "AL002", "municipio": "OLINDA", "ucs_total": 3}
    assert [a["id"] for a in repo.alimentadores()] == ["AL001", "AL002", "AL003"]


def test_alimentadores_filtra_por_municipio(repo):
    assert [a["id"] for a in repo.alimentadores("OLINDA")] == ["AL002"]
    assert repo.alimentadores("PAULISTA") == []


def test_competencias_vem_do_periodo_das_leituras(repo):
    comps = repo.competencias()
    assert comps[0] == "2022-07" and comps[-1] == "2026-06" and len(comps) == 48


# ---------- busca e cadastro ----------
def test_buscar_por_parte_do_id_respeita_limite_e_ordem(repo):
    assert [u["uc_id"] for u in repo.buscar_ucs("uc0000", None, None, 3)] == ["UC00001", "UC00002", "UC00003"]


def test_buscar_por_nome_ignora_acento_e_caixa(repo):
    assert [u["uc_id"] for u in repo.buscar_ucs("jose", None, None, 20)] == ["UC00002"]
    # "jose a" atravessa o acento: só casa se "JOSÉ A***" for comparado sem acento
    assert [u["uc_id"] for u in repo.buscar_ucs("jose a", None, None, 20)] == ["UC00002"]
    assert [u["uc_id"] for u in repo.buscar_ucs("JOSÉ A", None, None, 20)] == ["UC00002"]


def test_buscar_trata_percent_e_underscore_como_texto(repo):
    assert repo.buscar_ucs("%", None, None, 20) == []
    assert repo.buscar_ucs("_", None, None, 20) == []


def test_buscar_com_filtros(repo):
    assert [u["uc_id"] for u in repo.buscar_ucs(None, "OLINDA", None, 20)] == ["UC00002", "UC00004"]
    assert [u["uc_id"] for u in repo.buscar_ucs(None, None, "RURAL", 20)] == ["UC00005"]
    assert repo.buscar_ucs("xyz", None, None, 20) == []


def test_uc_ignora_caixa_e_devolve_so_dado_mascarado(repo):
    uc = repo.uc("uc00001")
    assert uc["uc_id"] == "UC00001" and uc["titular"] == "JOAO S***"
    assert uc["alimentador_id"] == "AL001" and uc["classe_descricao"] == "Residencial"
    assert uc["variacao_consumo_12m_pct"] == -9.75
    assert "nome_titular" not in uc and "cpf_cnpj" not in uc
    assert repo.uc("UC99999") is None


# ---------- medidor e geração distribuída ----------
def test_medidor_ativo(repo):
    m = repo.medidor_uc("UC00001")
    assert m == {
        "medidor_id": "M-UC00001", "tipo": "ELETRONICO", "modelo": "X1", "data_instalacao": "2020-01-10",
        "status": "ativo", "idade_anos": 6.5, "trocado_recentemente": False,
    }


def test_uc_sem_medidor_ativo_ou_inexistente_devolve_none(repo):
    assert repo.medidor_uc("UC00003") is None
    assert repo.medidor_uc("UC99999") is None


def test_gd_normal_e_gd_atipica_com_booleano_em_texto(repo):
    normal = repo.gd_uc("UC00001")
    assert normal["potencia_kwp"] == 5.5 and normal["modalidade"] == "AUTOCONSUMO LOCAL"
    assert normal["energia_injetada_atipica"] is False
    atipica = repo.gd_uc("UC00002")  # possui_gd e atipica gravados como o texto "true"
    assert atipica["energia_injetada_atipica"] is True and atipica["energia_injetada_media_kwh"] == 1089.0


def test_uc_sem_gd_devolve_none(repo):
    assert repo.gd_uc("UC00004") is None
    assert repo.gd_uc("UC99999") is None


# ---------- o que a Gold ainda não entrega ----------
def test_dados_sem_tabela_na_gold_levantam_erro_claro_em_vez_de_lista_vazia(repo):
    chamadas = {
        "fato_consumo_faturamento": [
            lambda: repo.faturas("2025-07", "2026-06"),
            lambda: repo.consumo_uc("UC00001"),
            lambda: repo.faturas_uc("UC00001"),
        ],
        "fato_atendimento": [lambda: repo.atendimentos_uc("UC00001")],
        "fato_interrupcao": [lambda: repo.ocorrencias("2025-07", "2026-06")],
        "fila_inspecao": [lambda: repo.suspeitas()],
    }
    for tabela, funcoes in chamadas.items():
        for f in funcoes:
            with pytest.raises(NaoDisponivelNaGold) as e:
                f()
            assert tabela in str(e.value)


# ---------- ordens de inspeção ficam no armazém do portal ----------
def test_ordens_delegam_para_o_armazem_do_portal(repo):
    o = repo.criar_ordem({"uc_id": "UC00001", "motivo": None, "observacoes": None})
    assert o["status"] == "PENDENTE" and [x["id"] for x in repo.listar_ordens()] == [o["id"]]
    assert repo.obter_ordem(o["id"])["uc_id"] == "UC00001"
    assert repo.atualizar_ordem(o["id"], {"status": "EM_CAMPO"})["status"] == "EM_CAMPO"
