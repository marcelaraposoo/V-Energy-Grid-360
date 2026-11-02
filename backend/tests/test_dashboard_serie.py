"""Série mensal A5/A3: competências reais, lacunas, filtros e contrato HTTP."""
from decimal import Decimal
import sqlite3

import pytest

from app.core.errors import NaoDisponivelNaGold
from app.repositories.dashboard import COLUNAS_KPIS, COLUNAS_SEGMENTOS
from app.repositories.sqlite_repo import SqliteRepository
from app.routers.deps import repo_dep
from app.schemas import Filtros, Periodo
from app.services.dashboard import serie
from tests.gold_fixture import criar_gold_db
from tests.test_dashboard_kpis import ATUAL, BASE, client, repo  # Fixtures A5/A3 compartilhadas.


def test_valores_mensais_globais_usam_a5_sem_acumular_e_sem_consultar_faturas(repo):
    pontos = serie(repo, Filtros(), (None, ATUAL))
    assert [p.model_dump() for p in pontos] == [
        dict(competencia="2026-01", receita=200, energia_kwh=100, tarifa_media=2),
        dict(competencia="2026-02", receita=1800, energia_kwh=300, tarifa_media=6),
    ]
    repo.kpis_mensais.assert_called_once_with("2026-01", "2026-02")
    repo.segmentos_mensais.assert_not_called()
    repo.faturas.assert_not_called()
    repo.indicadores_continuidade.assert_not_called()


@pytest.mark.parametrize("filtros", [
    Filtros(municipio="Recife"), Filtros(classe="RESIDENCIAL"),
    Filtros(municipio="Recife", bairro="Centro", classe="RESIDENCIAL"),
])
def test_recortes_agregam_a3_por_competencia_e_respeitam_bairros_homonimos(repo, filtros):
    pontos = serie(repo, filtros, (None, ATUAL))
    assert [(p.receita, p.energia_kwh, p.tarifa_media) for p in pontos] == [(80, 40, 2), (720, 120, 6)]
    repo.segmentos_mensais.assert_called_once_with("2026-01", "2026-02", filtros.municipio, filtros.bairro, filtros.classe)
    repo.kpis_mensais.assert_not_called()


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife")])
def test_comparacao_consulta_so_os_intervalos_pedidos_e_preserva_datas_reais(repo, filtros):
    pontos = serie(repo, filtros, (BASE, ATUAL))
    assert [p.competencia for p in pontos] == ["2025-01", "2025-02", "2026-01", "2026-02"]
    leitura = repo.segmentos_mensais if filtros.municipio else repo.kpis_mensais
    assert [tuple(c.args[:2]) for c in leitura.call_args_list] == [("2025-01", "2025-02"), ("2026-01", "2026-02")]
    assert [p.receita for p in pontos] == ([40, 360, 80, 720] if filtros.municipio else [100, 900, 200, 1800])


def test_comparacao_com_referencia_posterior_continua_ordenada_por_competencia(repo):
    assert [p.competencia for p in serie(repo, Filtros(), (ATUAL, BASE))] == ["2025-01", "2025-02", "2026-01", "2026-02"]


def test_sem_periodos_explicitos_preserva_catalogo_inteiro_e_nao_inventa_zeros(repo):
    pontos = serie(repo, Filtros())
    assert len(pontos) == 48
    assert pontos[0].competencia == "2022-07" and pontos[-1].competencia == "2026-06"
    assert sum(p.receita is not None for p in pontos) == 4
    assert pontos[0].receita is pontos[0].energia_kwh is pontos[0].tarifa_media is None
    repo.kpis_mensais.assert_called_once_with("2022-07", "2026-06")


def test_catalogo_vazio_retorna_lista_vazia_sem_consulta_mensal(repo):
    repo.competencias = lambda: []
    assert serie(repo, Filtros()) == []
    repo.kpis_mensais.assert_not_called()


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife")])
def test_mes_ausente_mantem_posicao_com_valores_nulos_sem_substituir_competencia(repo, filtros):
    if filtros.municipio:
        repo.segmentos[:] = [r for r in repo.segmentos if not (r["municipio"] == "Recife" and r["mes_referencia"] == "2026-01")]
    else:
        repo.mensais.pop(2)
    janeiro, fevereiro = serie(repo, filtros, (None, ATUAL))
    assert janeiro.model_dump() == dict(competencia="2026-01", receita=None, energia_kwh=None, tarifa_media=None)
    assert fevereiro.competencia == "2026-02" and fevereiro.receita is not None


@pytest.mark.parametrize(("coluna", "receita", "consumo"), [
    ("receita_energia", None, 300), ("consumo_total_kwh", 1800, None),
])
def test_campo_nulo_invalida_apenas_a_metrica_e_o_preco_dependente(repo, coluna, receita, consumo):
    repo.mensais[3][coluna] = None
    ponto = serie(repo, Filtros(), (None, Periodo(inicio="2026-02", fim="2026-02")))[0]
    assert ponto.receita == receita and ponto.energia_kwh == consumo
    assert ponto.tarifa_media is None


@pytest.mark.parametrize(("receita", "consumo", "preco"), [(0, 0, None), (100, 0, None), (0, 100, 0)])
def test_zero_presente_nao_vira_lacuna_e_consumo_zero_nao_produz_preco(repo, receita, consumo, preco):
    repo.mensais[3].update(receita_energia=receita, consumo_total_kwh=consumo)
    ponto = serie(repo, Filtros(), (None, Periodo(inicio="2026-02", fim="2026-02")))[0]
    assert ponto.receita == receita and ponto.energia_kwh == consumo and ponto.tarifa_media == preco


def test_mes_isolado_retorna_um_ponto_e_precisao_consistente_com_kpis(repo):
    repo.mensais[3].update(receita_energia=Decimal("1"), consumo_total_kwh=Decimal("3.125"))
    ponto, = serie(repo, Filtros(), (None, Periodo(inicio="2026-02", fim="2026-02")))
    assert ponto.receita == 1 and ponto.energia_kwh == 3.13
    assert ponto.tarifa_media == 0.32  # Divisão usa os valores originais, antes de arredondar o consumo.


def test_segmentos_somam_dinheiro_antes_de_dividir_em_vez_de_media_dos_precos(repo):
    recife = next(r for r in repo.segmentos if r["municipio"] == "Recife" and r["mes_referencia"] == "2026-01")
    recife.update(receita_energia=Decimal("0.1"), consumo_kwh=1)
    repo.segmentos.append({**recife, "classe": "COMERCIAL", "receita_energia": Decimal("0.2"), "consumo_kwh": 3})
    ponto, = serie(repo, Filtros(municipio="Recife"), (None, Periodo(inicio="2026-01", fim="2026-01")))
    assert ponto.receita == 0.3 and ponto.energia_kwh == 4 and ponto.tarifa_media == 0.075


def test_indisponibilidade_de_gold_nao_e_mascarada_com_serie_de_zeros(repo):
    repo.kpis_mensais.side_effect = NaoDisponivelNaGold("kpis_mensal")
    with pytest.raises(NaoDisponivelNaGold, match="kpis_mensal"):
        serie(repo, Filtros(), (None, ATUAL))


@pytest.fixture
def sqlite_repo(tmp_path, repo):
    path = criar_gold_db(tmp_path / "gold.db")
    with sqlite3.connect(path) as con:
        for tabela, colunas, linhas in (
            ("kpis_mensal", COLUNAS_KPIS, repo.mensais),
            ("fato_segmento_mensal", COLUNAS_SEGMENTOS, repo.segmentos),
        ):
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})", [
                [float(r[c]) if isinstance(r.get(c), Decimal) else r.get(c) for c in colunas] for r in linhas
            ])
    return SqliteRepository(path)


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife", bairro="Centro", classe="RESIDENCIAL")])
def test_sqlite_equivale_ao_mock_sem_fatos_de_faturas_nem_continuidade(repo, sqlite_repo, filtros):
    for periodos in (None, (None, ATUAL), (BASE, ATUAL)):
        assert serie(sqlite_repo, filtros, periodos) == serie(repo, filtros, periodos)


def test_endpoint_sem_parametros_mantem_48_meses_e_campos_da_resposta(client):
    resposta = client.get("/api/dashboard/serie")
    assert resposta.status_code == 200
    assert len(resposta.json()) == 48
    assert resposta.json()[0] == dict(competencia="2022-07", receita=None, energia_kwh=None, tarifa_media=None)


@pytest.mark.parametrize("comparar", [True, False])
def test_endpoint_recorta_periodos_com_filtros_e_comparacao_opcional(client, comparar):
    resposta = client.get("/api/dashboard/serie", params={
        "comparar": comparar, "atual_inicio": "2026-01", "atual_fim": "2026-02",
        "municipio": "Recife", "bairro": "Centro", "classe": "RESIDENCIAL",
    })
    assert resposta.status_code == 200
    assert [p["competencia"] for p in resposta.json()] == (["2025-01", "2025-02", "2026-01", "2026-02"] if comparar else ["2026-01", "2026-02"])
    assert resposta.json()[-1] == dict(competencia="2026-02", receita=720, energia_kwh=120, tarifa_media=6)


def test_endpoint_serializa_lacuna_como_null_sem_condensar_meses(client, repo):
    repo.mensais.pop(2)
    resposta = client.get("/api/dashboard/serie", params={"comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-02"})
    assert resposta.status_code == 200
    assert resposta.json() == [
        dict(competencia="2026-01", receita=None, energia_kwh=None, tarifa_media=None),
        dict(competencia="2026-02", receita=1800, energia_kwh=300, tarifa_media=6),
    ]


def test_endpoint_funciona_com_sqlite_sem_faturas_globais(client, sqlite_repo):
    client.app.dependency_overrides[repo_dep] = lambda: sqlite_repo
    resposta = client.get("/api/dashboard/serie", params={"comparar": False, "atual_inicio": "2026-01", "atual_fim": "2026-02"})
    assert resposta.status_code == 200
    assert [p["receita"] for p in resposta.json()] == [200, 1800]


@pytest.mark.parametrize("params", [
    {"atual_inicio": "2026-01"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-02", "base_inicio": "2026-02", "base_fim": "2026-03"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-02", "base_inicio": "2025-01", "base_fim": "2025-01"},
    {"comparar": False, "atual_inicio": "2024-01", "atual_fim": "2026-06"},
    {"comparar": False, "atual_inicio": "2022-06", "atual_fim": "2022-06"},
    {"municipio": "desconhecido"},
])
def test_endpoint_preserva_validacoes_existentes(client, params):
    assert client.get("/api/dashboard/serie", params=params).status_code == 422
