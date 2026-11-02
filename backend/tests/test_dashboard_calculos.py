"""Cálculos do Dashboard a partir das agregadas A5/A3, sem acesso HTTP."""
from datetime import date
from decimal import Decimal
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.errors import NaoDisponivelNaGold
from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.schemas import Filtros, Periodo
from app.services.dashboard import (
    MetricasMes, calcular_periodo, comparar_indicadores, metricas_mensais,
)
from tests.gold_fixture import criar_gold_db


@pytest.fixture
def periodo():
    return Periodo(inicio="2026-01", fim="2026-02")


def test_leitura_global_preserva_valores_auditados_da_a5(periodo):
    repo = SimpleNamespace(kpis_mensais=Mock(return_value=[{
        "mes_referencia": "2026-02", "receita_energia": 900, "consumo_total_kwh": 300,
        "qtd_ucs_faturadas": 8, "inadimplencia_pct": 6.25,
    }, {
        "mes_referencia": "2026-01", "receita_energia": 100, "consumo_total_kwh": 100,
        "qtd_ucs_faturadas": 10, "inadimplencia_pct": None,
    }]), segmentos_mensais=Mock(side_effect=AssertionError("A visão geral deve usar A5")))
    resultado = metricas_mensais(repo, periodo, Filtros())
    assert list(resultado) == ["2026-01", "2026-02"]
    assert resultado["2026-02"] == MetricasMes(Decimal(900), Decimal(300), 8, Decimal("6.25"))
    assert resultado["2026-01"].inadimplencia_pct is None
    repo.kpis_mensais.assert_called_once_with("2026-01", "2026-02")


@pytest.mark.parametrize("filtros", [
    Filtros(municipio="Recife"), Filtros(classe="RESIDENCIAL"),
    Filtros(municipio="Recife", bairro="Centro", classe="COMERCIAL"),
])
def test_segmentos_somam_antes_de_calcular_inadimplencia(periodo, filtros):
    repo = SimpleNamespace(segmentos_mensais=Mock(return_value=[{
        "mes_referencia": "2026-02", "receita_energia": 0.1, "consumo_kwh": 100,
        "qtd_ucs_faturadas": 1, "receita_total": 100, "valor_em_aberto": 100,
    }, {
        "mes_referencia": "2026-02", "receita_energia": 0.2, "consumo_kwh": 200,
        "qtd_ucs_faturadas": 3, "receita_total": 900, "valor_em_aberto": 0,
    }]), kpis_mensais=Mock(side_effect=AssertionError("O recorte deve usar A3")))
    resultado = metricas_mensais(repo, periodo, filtros)
    # Taxas dos segmentos: 100% e 0%; a taxa correta é 10%, não 50%.
    assert resultado == {"2026-02": MetricasMes(Decimal("0.3"), Decimal(300), 4, Decimal(10))}
    repo.segmentos_mensais.assert_called_once_with(
        "2026-01", "2026-02", filtros.municipio, filtros.bairro, filtros.classe,
    )


@pytest.mark.parametrize(("total", "aberto", "esperado"), [(0, 0, None), (100, None, None), (100, 0, Decimal(0))])
def test_razao_indefinida_e_nulo_nao_viram_zero(periodo, total, aberto, esperado):
    repo = SimpleNamespace(segmentos_mensais=Mock(return_value=[{
        "mes_referencia": "2026-02", "receita_energia": None, "consumo_kwh": 0,
        "qtd_ucs_faturadas": None, "receita_total": total, "valor_em_aberto": aberto,
    }]))
    resultado = metricas_mensais(repo, periodo, Filtros(classe="COMERCIAL"))["2026-02"]
    assert resultado == MetricasMes(None, Decimal(0), None, esperado)


def test_consulta_vazia_nao_inventa_competencias(periodo):
    repo = SimpleNamespace(kpis_mensais=Mock(return_value=[]))
    assert metricas_mensais(repo, periodo, Filtros()) == {}


def test_indisponibilidade_da_tabela_e_propagada(periodo):
    repo = SimpleNamespace(kpis_mensais=Mock(side_effect=NaoDisponivelNaGold("kpis_mensal")))
    with pytest.raises(NaoDisponivelNaGold, match="kpis_mensal"):
        metricas_mensais(repo, periodo, Filtros())


def test_duplicidade_no_grao_global_nao_duplica_valores(periodo):
    repo = SimpleNamespace(kpis_mensais=Mock(return_value=[{"mes_referencia": "2026-02"}] * 2))
    with pytest.raises(ValueError, match="mais de uma linha"):
        metricas_mensais(repo, periodo, Filtros())


@pytest.fixture
def agregadas():
    return [
        {"mes_referencia": mes, "receita_energia": receita, "consumo_total_kwh": consumo,
         "qtd_ucs_faturadas": ucs, "inadimplencia_pct": taxa}
        for mes, receita, consumo, ucs, taxa in [
            ("2025-01", 100, 100, 10, 30), ("2025-02", 900, 300, 8, 5),
            ("2026-01", 200, 100, 12, 20), ("2026-02", 1800, 300, 9, 6),
        ]
    ]


@pytest.fixture
def repo_agregadas(agregadas):
    return SimpleNamespace(kpis_mensais=Mock(side_effect=lambda inicio, fim: [
        r for r in agregadas if inicio <= r["mes_referencia"] <= fim
    ]))


def test_periodo_soma_receita_e_consumo_e_usa_posicao_no_mes_final(repo_agregadas, periodo):
    resultado = calcular_periodo(repo_agregadas, periodo, Filtros())
    assert resultado.receita_energia == Decimal(2000)
    assert resultado.consumo_kwh == Decimal(400)
    # Preços mensais: 2 e 6; preço acumulado: 2000/400 = 5, não a média 4.
    assert resultado.preco_medio_kwh == Decimal(5)
    assert resultado.qtd_ucs_faturadas == 9
    assert resultado.inadimplencia_pct == Decimal(6)
    assert resultado.competencias_ausentes == ()
    assert resultado.competencia_posicao == "2026-02"
    assert resultado.data_corte == date(2026, 6, 30)
    assert resultado.fonte == "kpis_mensal"


def test_comparacao_usa_periodos_escolhidos_e_inadimplencia_em_pontos_percentuais(repo_agregadas, periodo):
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-02"), Filtros())
    atual = calcular_periodo(repo_agregadas, periodo, Filtros())
    comparacao = comparar_indicadores(base, atual)
    assert comparacao["receita_energia"].variacao_abs == Decimal(1000)
    assert comparacao["receita_energia"].variacao_pct == Decimal(100)
    assert comparacao["consumo_kwh"].variacao_pct == Decimal(0)
    assert comparacao["preco_medio_kwh"].variacao_abs == Decimal("2.5")
    assert comparacao["preco_medio_kwh"].variacao_pct == Decimal(100)
    assert comparacao["qtd_ucs_faturadas"].variacao_abs == Decimal(1)
    assert comparacao["qtd_ucs_faturadas"].variacao_pct == Decimal("12.5")
    inadimplencia = comparacao["inadimplencia_pct"]
    assert inadimplencia.valor_base == Decimal(5)
    assert inadimplencia.valor_atual == Decimal(6)
    assert inadimplencia.variacao_pp == Decimal(1)
    assert inadimplencia.variacao_pct is inadimplencia.variacao_abs is None
    assert all(m.variacao_pp is None for nome, m in comparacao.items() if nome != "inadimplencia_pct")


def test_acumulado_incompleto_fica_indisponivel_sem_invalidar_posicao_final(repo_agregadas):
    resultado = calcular_periodo(repo_agregadas, Periodo(inicio="2025-12", fim="2026-02"), Filtros())
    assert resultado.competencias_ausentes == ("2025-12",)
    assert resultado.receita_energia is resultado.consumo_kwh is resultado.preco_medio_kwh is None
    assert resultado.qtd_ucs_faturadas == 9 and resultado.inadimplencia_pct == Decimal(6)


def test_base_incompleta_impede_comparar_totais_mas_preserva_comparacao_da_posicao_final(
    repo_agregadas, agregadas, periodo,
):
    agregadas.pop(0)
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-02"), Filtros())
    atual = calcular_periodo(repo_agregadas, periodo, Filtros())
    comparacao = comparar_indicadores(base, atual)
    assert comparacao["receita_energia"].valor_base is None
    assert comparacao["receita_energia"].valor_atual == Decimal(2000)
    assert comparacao["receita_energia"].variacao_abs is comparacao["receita_energia"].variacao_pct is None
    assert comparacao["consumo_kwh"].variacao_pct is None
    assert comparacao["preco_medio_kwh"].variacao_pct is None
    assert comparacao["qtd_ucs_faturadas"].variacao_pct == Decimal("12.5")
    assert comparacao["inadimplencia_pct"].variacao_pp == Decimal(1)


def test_mes_final_ausente_nao_e_substituido_por_outro_mes(repo_agregadas):
    resultado = calcular_periodo(repo_agregadas, Periodo(inicio="2026-01", fim="2026-03"), Filtros())
    assert resultado.competencias_ausentes == ("2026-03",)
    assert resultado.receita_energia is resultado.consumo_kwh is resultado.preco_medio_kwh is None
    assert resultado.qtd_ucs_faturadas is resultado.inadimplencia_pct is None
    assert resultado.competencia_posicao == "2026-03"


def test_sem_historico_nao_gera_valores_ou_comparacoes_ficticios(repo_agregadas, periodo):
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2024-01", fim="2024-02"), Filtros())
    atual = calcular_periodo(repo_agregadas, periodo, Filtros())
    assert base.competencias_ausentes == ("2024-01", "2024-02")
    for m in comparar_indicadores(base, atual).values():
        assert m.valor_base is None and m.valor_atual is not None
        assert m.variacao_abs is m.variacao_pct is m.variacao_pp is None


def test_nulo_invalida_so_a_metrica_afetada_e_preco_dependente(repo_agregadas, agregadas, periodo):
    agregadas[-1]["consumo_total_kwh"] = None
    agregadas[-1]["qtd_ucs_faturadas"] = None
    resultado = calcular_periodo(repo_agregadas, periodo, Filtros())
    assert resultado.competencias_ausentes == ()
    assert resultado.receita_energia == Decimal(2000)
    assert resultado.consumo_kwh is resultado.preco_medio_kwh is resultado.qtd_ucs_faturadas is None
    assert resultado.inadimplencia_pct == Decimal(6)


def test_referencia_zero_mantem_diferenca_absoluta_e_nao_divide_por_zero(repo_agregadas, agregadas, periodo):
    for r in agregadas[:2]:
        r.update(receita_energia=0, consumo_total_kwh=0, qtd_ucs_faturadas=0, inadimplencia_pct=0)
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-02"), Filtros())
    atual = calcular_periodo(repo_agregadas, periodo, Filtros())
    comparacao = comparar_indicadores(base, atual)
    assert base.receita_energia == base.consumo_kwh == Decimal(0)
    assert base.preco_medio_kwh is None
    assert comparacao["receita_energia"].variacao_abs == Decimal(2000)
    assert comparacao["consumo_kwh"].variacao_abs == Decimal(400)
    assert comparacao["qtd_ucs_faturadas"].variacao_abs == Decimal(9)
    assert all(m.variacao_pct is None for m in comparacao.values())
    assert comparacao["inadimplencia_pct"].variacao_pp == Decimal(6)


def test_zero_atual_e_reducao_total_e_preco_zero_e_valido(repo_agregadas, agregadas, periodo):
    for r in agregadas[2:]:
        r["receita_energia"] = 0
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-02"), Filtros())
    atual = calcular_periodo(repo_agregadas, periodo, Filtros())
    comparacao = comparar_indicadores(base, atual)
    assert atual.preco_medio_kwh == Decimal(0)
    assert comparacao["receita_energia"].variacao_pct == Decimal(-100)
    assert comparacao["preco_medio_kwh"].variacao_pct == Decimal(-100)


def test_preco_nao_e_arredondado_antes_da_variacao(repo_agregadas, agregadas):
    agregadas[0].update(receita_energia=1, consumo_total_kwh=3)
    agregadas[-1].update(receita_energia=2, consumo_total_kwh=7)
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-01"), Filtros())
    atual = calcular_periodo(repo_agregadas, Periodo(inicio="2026-02", fim="2026-02"), Filtros())
    comparacao = comparar_indicadores(base, atual)["preco_medio_kwh"]
    assert base.preco_medio_kwh == Decimal(1) / Decimal(3)
    assert comparacao.variacao_abs == Decimal("-0.0476")
    assert comparacao.variacao_pct == Decimal("-14.29")


def test_percentual_arredonda_meio_para_cima(repo_agregadas, agregadas):
    agregadas[0]["receita_energia"] = 1000
    agregadas[-1]["receita_energia"] = 1000.05
    base = calcular_periodo(repo_agregadas, Periodo(inicio="2025-01", fim="2025-01"), Filtros())
    atual = calcular_periodo(repo_agregadas, Periodo(inicio="2026-02", fim="2026-02"), Filtros())
    assert comparar_indicadores(base, atual)["receita_energia"].variacao_pct == Decimal("0.01")


def test_periodo_segmentado_soma_mes_a_mes_sem_misturar_inadimplencia(periodo):
    repo = SimpleNamespace(segmentos_mensais=Mock(return_value=[
        {"mes_referencia": mes, "receita_energia": receita, "consumo_kwh": consumo,
         "qtd_ucs_faturadas": ucs, "receita_total": total, "valor_em_aberto": aberto}
        for mes, receita, consumo, ucs, total, aberto in [
            ("2026-01", 100, 100, 10, 1000, 900),
            ("2026-02", 100, 100, 2, 100, 100),
            ("2026-02", 800, 300, 5, 900, 0),
        ]
    ]))
    resultado = calcular_periodo(repo, periodo, Filtros(municipio="Recife"))
    assert resultado.receita_energia == Decimal(1000)
    assert resultado.consumo_kwh == Decimal(500)
    assert resultado.preco_medio_kwh == Decimal(2)
    assert resultado.qtd_ucs_faturadas == 7
    assert resultado.inadimplencia_pct == Decimal(10)
    assert resultado.fonte == "fato_segmento_mensal"


@pytest.mark.parametrize(("inicio", "fim"), [("2026-02", "2026-01"), ("2026-13", "2026-13")])
def test_periodo_invalido_e_rejeitado_antes_de_ler_o_repositorio(repo_agregadas, inicio, fim):
    with pytest.raises(ValueError):
        calcular_periodo(repo_agregadas, Periodo(inicio=inicio, fim=fim), Filtros())
    repo_agregadas.kpis_mensais.assert_not_called()


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife"), Filtros(classe="RESIDENCIAL")])
def test_calculos_equivalem_entre_mock_e_sqlite_com_as_agregadas_da_etapa_1(tmp_path, filtros):
    mock = MockRepository()
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        for tabela in ("kpis_mensal", "fato_segmento_mensal"):
            colunas = list(mock.d[tabela][0])
            con.execute(f"CREATE TABLE {tabela} ({', '.join(colunas)})")
            con.executemany(
                f"INSERT INTO {tabela} VALUES ({', '.join('?' for _ in colunas)})",
                [[r[c] for c in colunas] for r in mock.d[tabela]],
            )
    sqlite = SqliteRepository(path)
    for periodo in (Periodo(inicio="2022-07", fim="2023-06"), Periodo(inicio="2025-07", fim="2026-06")):
        assert calcular_periodo(sqlite, periodo, filtros) == calcular_periodo(mock, periodo, filtros)
