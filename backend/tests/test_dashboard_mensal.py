"""A3/A5: valores conferidos, grão mensal e equivalência de leitura mock/SQLite.

Usa SQLite fictício; não substitui a homologação da exportação oficial.
"""
import sqlite3
from types import SimpleNamespace

import pytest

from app.core.errors import NaoDisponivelNaGold
from app.mock.dashboard import build_fato_segmento_mensal, build_kpis_mensal
from app.mock.mock_data import build_mock_data
from app.repositories import mock_repo
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from tests.gold_fixture import criar_gold_db


def _fatura(uc, mes, kwh, energia, total, *, aberta=False, faixa="EM DIA", bandeira="Verde", troca=False):
    return {
        "id_uc": uc["id_uc"], "mes_referencia": mes,
        "municipio": uc["municipio"], "bairro": uc["bairro"], "classe": uc["classe"],
        "consumo_kwh": kwh, "valor_energia": energia, "valor_total": total,
        "em_aberto": aberta, "faixa_atraso": faixa, "bandeira_tarifaria": bandeira,
        "troca_medidor": troca,
        "possui_gd_no_mes": uc["possui_gd"] and mes >= uc["data_conexao_gd"][:7],
    }


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    ucs = [
        {"id_uc": "UC000001", "nome_titular_mascarado": "ANA S***", "municipio": "Recife",
         "bairro": "Centro", "classe": "RESIDENCIAL", "alimentador": "AL1",
         "data_ligacao": "2020-01-01", "possui_gd": True, "data_conexao_gd": "2026-06-20"},
        {"id_uc": "UC000002", "nome_titular_mascarado": "BRUNO S***", "municipio": "Olinda",
         "bairro": "Centro", "classe": "RESIDENCIAL", "alimentador": "AL2",
         "data_ligacao": "2020-01-01", "possui_gd": False, "data_conexao_gd": None},
        {"id_uc": "UC000003", "nome_titular_mascarado": "CARLA S***", "municipio": "Recife",
         "bairro": "Centro", "classe": "COMERCIAL", "alimentador": "AL1",
         "data_ligacao": "2026-06-01", "possui_gd": False, "data_conexao_gd": None},
        {"id_uc": "UC000004", "nome_titular_mascarado": "DANILO S***", "municipio": "Recife",
         "bairro": "Centro", "classe": "RESIDENCIAL", "alimentador": "AL1",
         "data_ligacao": "2026-06-30", "possui_gd": False, "data_conexao_gd": None},
    ]
    comps = ["2025-06", "2026-01", "2026-02", "2026-05", "2026-06"]
    faturas = [
        _fatura(ucs[0], "2025-06", 100, 50, 60),
        _fatura(ucs[1], "2025-06", 200, 100, 120, aberta=True, faixa="MAIS DE 90 DIAS"),
        _fatura(ucs[0], "2026-01", 150, 100, 150, aberta=True, faixa="MAIS DE 90 DIAS"),
        _fatura(ucs[0], "2026-02", 0, 0, 0),
        # Em aberto e ainda em dia: também entra na inadimplência contratada.
        _fatura(ucs[0], "2026-06", 100, 80, 100, aberta=True, bandeira="Amarela"),
        _fatura(ucs[1], "2026-06", 200, 120, 300),
        _fatura(ucs[2], "2026-06", 50, 100, 100, aberta=True, faixa="ATE 30 DIAS", bandeira="Vermelha P2", troca=True),
    ]
    interrupcoes = [{"mes_referencia": "2026-06", "duracao_min": m} for m in (60, 120)]
    atendimentos = [{"mes_referencia": "2026-06", "nota_satisfacao": n} for n in (None, 2, 5)]
    dados = {
        "dim_uc": ucs, "fato_consumo_faturamento": faturas,
        "fato_segmento_mensal": build_fato_segmento_mensal(ucs, faturas, comps),
        "kpis_mensal": build_kpis_mensal(ucs, faturas, interrupcoes, atendimentos, comps),
    }
    monkeypatch.setattr(mock_repo, "build_mock_data", lambda: dados)
    mock = MockRepository()
    path = criar_gold_db(tmp_path / "gold.db", ucs=ucs)
    with sqlite3.connect(path) as con:
        # Só exporta as agregadas: a leitura do Dashboard não depende das fatos por UC.
        for tabela in ("kpis_mensal", "fato_segmento_mensal"):
            colunas = list(dados[tabela][0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(
                f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                [[r[c] for c in colunas] for r in reversed(dados[tabela])],
            )
    return SimpleNamespace(mock=mock, sqlite=SqliteRepository(path), path=path)


@pytest.fixture(params=["mock", "sqlite"])
def repo(cenario, request):
    return getattr(cenario, request.param)


def test_kpis_mensais_preservam_as_20_colunas_e_valores_da_a5(repo):
    assert repo.kpis_mensais("2026-06", "2026-06") == [{
        "mes_referencia": "2026-06", "qtd_ucs_cadastradas": 4, "qtd_ucs_faturadas": 3,
        "consumo_total_kwh": 350.0, "receita_energia": 300.0, "receita_total": 500.0,
        "preco_medio_kwh": 0.8571, "bandeira_predominante": "Amarela",
        "pct_faturas_bandeira_nao_verde": 66.67, "qtd_faturas_em_aberto": 2,
        "inadimplencia_pct": 40.0, "valor_em_aberto_mais_90_dias": 0.0, "qtd_ucs_com_gd": 1,
        "qtd_interrupcoes": 2, "dec_horas": 0.75, "fec": 0.5,
        "qtd_atendimentos": 3, "nota_satisfacao_media": 3.5,
        "variacao_consumo_ano_anterior_pct": 16.67, "variacao_receita_ano_anterior_pct": 100.0,
    }]


def test_segmentos_preservam_as_16_colunas_e_cadastro_sem_fatura(repo):
    assert repo.segmentos_mensais("2026-06", "2026-06", "Recife", "Centro", "RESIDENCIAL") == [{
        "mes_referencia": "2026-06", "municipio": "Recife", "bairro": "Centro", "classe": "RESIDENCIAL",
        "qtd_ucs_cadastradas": 2, "qtd_ucs_faturadas": 1, "qtd_ucs_com_gd": 1,
        "consumo_kwh": 100.0, "consumo_kwh_ucs_com_gd": 100.0,
        "receita_energia": 80.0, "receita_total": 100.0, "qtd_faturas": 1,
        "qtd_faturas_em_aberto": 1, "valor_em_aberto": 100.0,
        "qtd_faturas_bandeira_nao_verde": 1, "qtd_trocas_medidor": 0,
    }]
    comercial = repo.segmentos_mensais("2026-06", "2026-06", classe="COMERCIAL")
    assert len(comercial) == 1 and comercial[0]["qtd_trocas_medidor"] == 1
    assert repo.segmentos_mensais("2025-06", "2026-02", classe="COMERCIAL") == []


def test_filtros_nao_misturam_bairros_homonimos_e_aceitam_classe_isolada(repo):
    olinda = repo.segmentos_mensais("2026-06", "2026-06", "Olinda", "Centro")
    assert len(olinda) == 1 and olinda[0]["receita_energia"] == 120
    recife = repo.segmentos_mensais("2026-06", "2026-06", municipio="Recife")
    assert {r["classe"] for r in recife} == {"RESIDENCIAL", "COMERCIAL"}
    residencial = repo.segmentos_mensais("2026-06", "2026-06", classe="RESIDENCIAL")
    assert {r["municipio"] for r in residencial} == {"Recife", "Olinda"}
    assert repo.segmentos_mensais("2026-06", "2026-06", "Olinda", classe="COMERCIAL") == []
    with pytest.raises(ValueError, match="bairro exige município"):
        repo.segmentos_mensais("2026-06", "2026-06", bairro="Centro")


def test_periodo_inclusivo_ordenacao_e_lacunas_sem_preenchimento(repo):
    linhas = repo.kpis_mensais("2026-01", "2026-06")
    assert [r["mes_referencia"] for r in linhas] == ["2026-01", "2026-02", "2026-06"]
    assert linhas[0]["valor_em_aberto_mais_90_dias"] == 150
    assert linhas[0]["qtd_ucs_com_gd"] == 0
    assert repo.kpis_mensais("2026-05", "2026-05") == []
    assert repo.kpis_mensais("2030-01", "2030-12") == []
    assert repo.segmentos_mensais("2030-01", "2030-12") == []
    segmentos = repo.segmentos_mensais("2026-01", "2026-06")
    chaves = [(r["mes_referencia"], r["municipio"], r["bairro"], r["classe"]) for r in segmentos]
    assert chaves == sorted(set(chaves))


def test_zeros_nulos_e_referencia_anual_sao_preservados(repo):
    primeiro = repo.kpis_mensais("2025-06", "2025-06")[0]
    assert primeiro["variacao_consumo_ano_anterior_pct"] is None
    assert primeiro["variacao_receita_ano_anterior_pct"] is None
    assert primeiro["nota_satisfacao_media"] is None
    janeiro = repo.kpis_mensais("2026-01", "2026-01")[0]
    assert janeiro["variacao_consumo_ano_anterior_pct"] is None
    assert janeiro["variacao_receita_ano_anterior_pct"] is None
    zero = repo.kpis_mensais("2026-02", "2026-02")[0]
    assert zero["consumo_total_kwh"] == zero["receita_energia"] == 0
    assert zero["preco_medio_kwh"] is zero["inadimplencia_pct"] is None
    assert zero["dec_horas"] == zero["fec"] == zero["qtd_atendimentos"] == 0


def test_sqlite_equivale_ao_mock_nas_duas_tabelas(cenario):
    assert cenario.sqlite.kpis_mensais("2025-06", "2026-06") == cenario.mock.kpis_mensais("2025-06", "2026-06")
    assert cenario.sqlite.segmentos_mensais("2025-06", "2026-06") == cenario.mock.segmentos_mensais("2025-06", "2026-06")


def test_sqlite_preserva_valores_exportados_sem_recalcular_e_normaliza_numeros(cenario):
    with sqlite3.connect(cenario.path) as con:
        con.execute("UPDATE kpis_mensal SET receita_energia = '987,65', qtd_ucs_faturadas = '7' WHERE mes_referencia = '2026-06'")
    registro = cenario.sqlite.kpis_mensais("2026-06", "2026-06")[0]
    assert registro["receita_energia"] == 987.65
    assert registro["qtd_ucs_faturadas"] == 7
    assert type(registro["qtd_ucs_faturadas"]) is int


def test_valores_dos_filtros_sql_sao_parametrizados(cenario):
    assert cenario.sqlite.segmentos_mensais("2025-06", "2026-06", municipio="Recife' OR 1=1 --") == []
    assert cenario.sqlite.segmentos_mensais("2025-06", "2026-06", classe="RESIDENCIAL' OR 1=1 --") == []
    assert len(cenario.sqlite.kpis_mensais("2026-06", "2026-06")) == 1


@pytest.mark.parametrize(("tabela", "metodo"), [
    ("kpis_mensal", "kpis_mensais"), ("fato_segmento_mensal", "segmentos_mensais"),
])
def test_tabela_ausente_informa_indisponibilidade_sem_afetar_a_outra(cenario, tabela, metodo):
    with sqlite3.connect(cenario.path) as con:
        con.execute(f"DROP TABLE {tabela}")
    with pytest.raises(NaoDisponivelNaGold, match=tabela):
        getattr(cenario.sqlite, metodo)("2025-06", "2026-06")
    outro = "segmentos_mensais" if metodo == "kpis_mensais" else "kpis_mensais"
    assert getattr(cenario.sqlite, outro)("2025-06", "2026-06")


@pytest.mark.parametrize(("tabela", "metodo"), [
    ("kpis_mensal", "kpis_mensais"), ("fato_segmento_mensal", "segmentos_mensais"),
])
def test_tabela_vazia_e_diferente_de_tabela_incompleta(cenario, tabela, metodo):
    with sqlite3.connect(cenario.path) as con:
        con.execute(f"DELETE FROM {tabela}")
    assert getattr(cenario.sqlite, metodo)("2025-06", "2026-06") == []
    with sqlite3.connect(cenario.path) as con:
        con.execute(f"ALTER TABLE {tabela} DROP COLUMN receita_energia")
    with pytest.raises(NaoDisponivelNaGold, match=f"{tabela}.*receita_energia"):
        getattr(cenario.sqlite, metodo)("2025-06", "2026-06")


def test_leitura_mock_nao_expoe_dicionarios_do_cache(cenario):
    cenario.mock.kpis_mensais("2026-06", "2026-06")[0]["receita_energia"] = -1
    cenario.mock.segmentos_mensais("2026-06", "2026-06")[0]["receita_energia"] = -1
    assert cenario.mock.kpis_mensais("2026-06", "2026-06")[0]["receita_energia"] == 300
    assert all(r["receita_energia"] >= 0 for r in cenario.mock.segmentos_mensais("2026-06", "2026-06"))


def test_mock_padrao_reconcilia_agregadas_com_fatos_ficticias():
    dados = build_mock_data()
    assert len(dados["kpis_mensal"]) == 48
    for kpi in dados["kpis_mensal"]:
        mes = kpi["mes_referencia"]
        segmentos = [r for r in dados["fato_segmento_mensal"] if r["mes_referencia"] == mes]
        faturas = [r for r in dados["fato_consumo_faturamento"] if r["mes_referencia"] == mes]
        assert sum(r["receita_energia"] for r in segmentos) == pytest.approx(sum(f["valor_energia"] for f in faturas))
        assert kpi["receita_energia"] == pytest.approx(sum(f["valor_energia"] for f in faturas))
        assert sum(r["consumo_kwh"] for r in segmentos) == kpi["consumo_total_kwh"]
        assert sum(r["qtd_ucs_faturadas"] for r in segmentos) == kpi["qtd_ucs_faturadas"] == 400
        assert sum(r["qtd_ucs_cadastradas"] for r in segmentos) == kpi["qtd_ucs_cadastradas"] == 400
        assert sum(r["qtd_ucs_com_gd"] for r in segmentos) == kpi["qtd_ucs_com_gd"]
        if mes <= "2023-06":
            assert kpi["variacao_consumo_ano_anterior_pct"] is None
            assert kpi["variacao_receita_ano_anterior_pct"] is None


def test_mock_soma_centavos_e_nao_calcula_variacao_contra_referencia_zero(cenario):
    ucs = cenario.mock.d["dim_uc"][:2]
    meses = ["2025-06", "2026-06"]
    faturas = [
        _fatura(ucs[0], "2025-06", 0, 0, 0),
        _fatura(ucs[0], "2026-06", 1, 0.1, 0.1, aberta=True),
        _fatura(ucs[1], "2026-06", 1, 0.2, 0.2, aberta=True),
    ]
    atual = build_kpis_mensal(ucs, faturas, [], [], meses)[-1]
    assert atual["receita_energia"] == atual["receita_total"] == 0.3
    assert atual["inadimplencia_pct"] == 100
    assert atual["variacao_receita_ano_anterior_pct"] is None
    assert atual["variacao_consumo_ano_anterior_pct"] is None
