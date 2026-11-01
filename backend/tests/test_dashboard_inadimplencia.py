"""Inadimplência do faturamento selecionado no corte fixo da Gold v4."""
from decimal import Decimal, ROUND_HALF_UP
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.repositories.mock_repo import MockRepository
from app.repositories.sqlite_repo import SqliteRepository
from app.schemas import Filtros, KpisResponse, Periodo
from app.services import dashboard
from tests.gold_fixture import criar_gold_db


def segmento(mes, total=1000, aberto=100, municipio="Recife", bairro="Centro", classe="RESIDENCIAL"):
    return dict(mes_referencia=mes, municipio=municipio, bairro=bairro, classe=classe,
                receita_total=total, valor_em_aberto=aberto, receita_energia=1)


def repositorio(linhas):
    return SimpleNamespace(
        segmentos_mensais=Mock(side_effect=lambda inicio, fim, *filtros: [
            r for r in linhas if inicio <= r["mes_referencia"] <= fim
        ]),
        kpis_mensais=Mock(side_effect=AssertionError("Não reconstruir dinheiro a partir de percentuais da A5")),
        faturas=Mock(side_effect=AssertionError("Não usar dias_atraso/status nem recalcular faturas")),
    )


def calcular(linhas, inicio="2026-01", fim="2026-02", filtros=None):
    return dashboard.calcular_inadimplencia_periodo(
        repositorio(linhas), Periodo(inicio=inicio, fim=fim), filtros or Filtros(),
    )


def test_soma_segmentos_e_competencias_antes_de_dividir_por_receita_com_tributos():
    resultado = calcular([
        segmento("2026-01", 100, 100), segmento("2026-01", 900, 0, bairro="Boa Viagem"),
        segmento("2026-02", 100, 20), segmento("2026-02", 1900, 0, bairro="Boa Viagem"),
        segmento("2025-12", 999999, 999999), segmento("2026-03", 999999, 999999),
    ])
    # Jan = 10%, fev = 1%. Consolidado = 120/3000 = 4%, não a média 5,5%.
    assert resultado.consolidado_pct == Decimal(4)
    assert resultado.ultima_competencia_pct == Decimal(1)
    assert resultado.competencias_ausentes == ()


@pytest.mark.parametrize("filtros", [Filtros(), Filtros(municipio="Recife"),
    Filtros(municipio="Recife", bairro="Centro"), Filtros(classe="COMERCIAL"),
    Filtros(municipio="Recife", bairro="Centro", classe="COMERCIAL")])
def test_todos_os_recortes_usam_a3_uma_unica_vez(filtros):
    repo = repositorio([segmento("2026-01")])
    resultado = dashboard.calcular_inadimplencia_periodo(repo, Periodo(inicio="2026-01", fim="2026-01"), filtros)
    assert resultado.consolidado_pct == resultado.ultima_competencia_pct == Decimal(10)
    repo.segmentos_mensais.assert_called_once_with("2026-01", "2026-01", filtros.municipio, filtros.bairro, filtros.classe)


@pytest.mark.parametrize(("meses", "ausentes", "ultima"), [
    (["2026-02"], ("2026-01",), Decimal(10)),
    (["2026-01"], ("2026-02",), None),
    ([], ("2026-01", "2026-02"), None),
])
def test_lacunas_invalidam_consolidado_e_nao_substituem_o_mes_final(meses, ausentes, ultima):
    resultado = calcular([segmento(mes) for mes in meses])
    assert resultado.consolidado_pct is None
    assert resultado.ultima_competencia_pct == ultima
    assert resultado.competencias_ausentes == ausentes


def test_mes_presente_com_zeros_nao_e_tratado_como_competencia_ausente():
    resultado = calcular([segmento("2026-01", 0, 0), segmento("2026-02", 100, 0)])
    assert resultado.consolidado_pct == resultado.ultima_competencia_pct == Decimal(0)
    assert resultado.competencias_ausentes == ()


def test_denominador_total_zero_e_indefinido_sem_classificar_o_mes_como_ausente():
    resultado = calcular([segmento("2026-01", 0, 0), segmento("2026-02", 0, 0)])
    assert resultado.consolidado_pct is resultado.ultima_competencia_pct is None
    assert resultado.competencias_ausentes == ()


def test_mes_final_com_faturamento_zero_nao_impede_consolidado_com_denominador_positivo():
    resultado = calcular([segmento("2026-01", 100, 10), segmento("2026-02", 0, 0)])
    assert resultado.consolidado_pct == Decimal(10)
    assert resultado.ultima_competencia_pct is None


@pytest.mark.parametrize("coluna", ["receita_total", "valor_em_aberto"])
@pytest.mark.parametrize("invalido", [None, "inválido", float("nan"), float("inf"), -1])
def test_valores_invalidos_nao_produzem_consolidado_parcial(coluna, invalido):
    primeiro = segmento("2026-01") | {coluna: invalido}
    resultado = calcular([primeiro, segmento("2026-02")])
    assert resultado.consolidado_pct is None
    assert resultado.ultima_competencia_pct == Decimal(10)
    assert resultado.competencias_ausentes == ()


def test_valor_nulo_em_um_segmento_nao_e_ignorado_na_agregacao_do_mes():
    resultado = calcular([segmento("2026-01"), segmento("2026-02"),
                          segmento("2026-02", aberto=None, bairro="Boa Viagem")])
    assert resultado.consolidado_pct is resultado.ultima_competencia_pct is None


def test_segmento_duplicado_e_reportado_em_vez_de_somar_duas_vezes():
    with pytest.raises(ValueError, match="segmento duplicado"):
        calcular([segmento("2026-01"), segmento("2026-01")])


def test_desconsidera_linhas_fora_do_intervalo_mesmo_se_repositorio_as_devolver():
    repo = SimpleNamespace(segmentos_mensais=Mock(return_value=[
        segmento("2025-12", aberto=1000), segmento("2026-01", aberto=100),
        segmento("2026-02", aberto=200), segmento("2026-03", aberto=1000),
    ]))
    resultado = dashboard.calcular_inadimplencia_periodo(repo, Periodo(inicio="2026-01", fim="2026-02"), Filtros())
    assert resultado.consolidado_pct == Decimal(15)


@pytest.mark.parametrize("meses", [1, 2])
def test_kpi_compara_consolidados_em_pp_sem_recalcular_outros_indicadores(monkeypatch, meses):
    principal = Periodo(inicio="2026-01", fim=f"2026-{meses:02d}")
    base = Periodo(inicio="2025-01", fim=f"2025-{meses:02d}")
    linhas = [segmento(f"{ano}-{mes:02d}", 1000, aberto)
              for ano, aberto in [(2025, 50), (2026, 60)] for mes in range(1, meses + 1)]
    repo = repositorio(linhas)
    monkeypatch.setattr(dashboard, "calcular_periodo", Mock(side_effect=AssertionError("Consulta exclusiva do indicador")))
    resposta = dashboard.kpis(repo, base, principal, Filtros(), indicador="inadimplencia")
    kpi, = resposta.kpis
    assert kpi.valor_atual == 6 and kpi.valor_base == 5 and kpi.variacao_pp == 1
    assert kpi.variacao_pct is kpi.variacao_abs is None
    assert kpi.inadimplencia.ultima_competencia == principal.fim
    assert kpi.inadimplencia.ultima_competencia_pct == 6
    assert kpi.inadimplencia.data_corte.isoformat() == "2026-06-30"
    assert repo.segmentos_mensais.call_count == 2
    assert KpisResponse.model_validate_json(resposta.model_dump_json()) == resposta


@pytest.mark.parametrize(("aberto_base", "esperado"), [(0, 6), (None, None)])
def test_base_zero_permite_pp_e_base_indisponivel_nao_permite(aberto_base, esperado):
    repo = repositorio([segmento("2025-01", aberto=aberto_base), segmento("2026-01", aberto=60)])
    kpi, = dashboard.kpis(repo, Periodo(inicio="2025-01", fim="2025-01"),
                         Periodo(inicio="2026-01", fim="2026-01"), Filtros(), indicador="inadimplencia").kpis
    assert kpi.variacao_pp == esperado


def test_base_incompleta_suprime_pp_e_atual_incompleto_preserva_ultima_competencia():
    repo = repositorio([segmento("2025-02"), segmento("2026-02", aberto=60)])
    kpi, = dashboard.kpis(repo, Periodo(inicio="2025-01", fim="2025-02"),
                         Periodo(inicio="2026-01", fim="2026-02"), Filtros(), indicador="inadimplencia").kpis
    assert kpi.valor_atual is kpi.valor_base is kpi.variacao_pp is None
    assert kpi.inadimplencia.ultima_competencia_pct == 6
    assert kpi.inadimplencia.competencias_ausentes == ["2026-01"]
    assert kpi.inadimplencia.competencias_ausentes_base == ["2025-01"]


def test_sem_comparacao_nao_consulta_referencia_nem_produz_pp():
    repo = repositorio([segmento("2026-01", aberto=0)])
    kpi, = dashboard.kpis(repo, None, Periodo(inicio="2026-01", fim="2026-01"), Filtros(), indicador="inadimplencia").kpis
    assert kpi.valor_atual == kpi.inadimplencia.ultima_competencia_pct == 0
    assert kpi.valor_base is kpi.variacao_pp is kpi.inadimplencia.competencias_ausentes_base is None
    repo.segmentos_mensais.assert_called_once()


def test_consulta_completa_preserva_inadimplencia_e_o_resumo_de_continuidade():
    repo = repositorio([segmento("2026-01")])
    repo.kpis_mensais = Mock(return_value=[{
        "mes_referencia": "2026-01", "receita_energia": 100, "consumo_total_kwh": 200,
        "qtd_ucs_faturadas": 10, "inadimplencia_pct": 10,
    }])
    repo.indicadores_continuidade = Mock(return_value=[{
        "mes_referencia": "2026-01", "qtd_ucs_alimentador_mes": 10, "dec_horas": 1, "fec": 2,
        "qtd_interrupcoes": 20, "horas_interrompidas": 10,
    }])
    resposta = dashboard.kpis(repo, None,
                             Periodo(inicio="2026-01", fim="2026-01"), Filtros())
    assert [(k.nome, k.valor_atual) for k in resposta.kpis if k.nome != "Inadimplência"] == [
        ("Receita faturada", 100), ("Energia faturada", 200), ("Tarifa média efetiva", 0.5),
        ("UCs faturadas", 10), ("DEC (simplificado)", 1), ("FEC (simplificado)", 2),
    ]
    inadimplencia = next(k for k in resposta.kpis if k.nome == "Inadimplência")
    assert inadimplencia.valor_atual == inadimplencia.inadimplencia.ultima_competencia_pct == 10
    repo.segmentos_mensais.assert_called_once()


@pytest.fixture(scope="module")
def mock():
    return MockRepository()


def test_a3_reconcilia_com_percentuais_e_faturamento_da_a5_em_todos_os_meses(mock):
    for mensal in mock.kpis_mensais("2022-07", "2026-06"):
        mes = mensal["mes_referencia"]
        resultado = dashboard.calcular_inadimplencia_periodo(mock, Periodo(inicio=mes, fim=mes), Filtros())
        assert resultado.consolidado_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == Decimal(str(mensal["inadimplencia_pct"]))
        segmentos = mock.segmentos_mensais(mes, mes)
        assert sum(Decimal(str(r["receita_total"])) for r in segmentos) == Decimal(str(mensal["receita_total"]))


def test_mock_inclui_abertas_ainda_nao_vencidas_e_exclui_pagas_com_atraso(mock):
    faturas = [f for f in mock.d["fato_consumo_faturamento"] if "2026-05" <= f["mes_referencia"] <= "2026-06"]
    assert any(f["em_aberto"] and f["faixa_atraso"] == "EM DIA" for f in faturas)
    assert any(not f["em_aberto"] and f["dias_atraso"] > 0 for f in faturas)
    aberto = sum(Decimal(str(f["valor_total"])) for f in faturas if f["em_aberto"])
    faturado = sum(Decimal(str(f["valor_total"])) for f in faturas)
    resultado = dashboard.calcular_inadimplencia_periodo(mock, Periodo(inicio="2026-05", fim="2026-06"), Filtros())
    assert resultado.consolidado_pct == aberto * 100 / faturado
    assert resultado.ultima_competencia_pct == 100  # Junho vence em julho no mock e continua em aberto no corte.


def test_sqlite_sem_fatos_globais_suporta_a_consulta_exclusiva_e_equivale_ao_mock(tmp_path, mock):
    path = criar_gold_db(tmp_path / "gold.db", ucs=mock.d["dim_uc"])
    with sqlite3.connect(path) as con:
        colunas = list(mock.d["fato_segmento_mensal"][0])
        con.execute(f"CREATE TABLE fato_segmento_mensal ({', '.join(colunas)})")
        con.executemany(f"INSERT INTO fato_segmento_mensal VALUES ({', '.join('?' for _ in colunas)})",
                        [[r[c] for c in colunas] for r in mock.d["fato_segmento_mensal"]])
    for filtros in (Filtros(), Filtros(municipio="Recife"), Filtros(municipio="Recife", bairro="Centro", classe="COMERCIAL")):
        base = Periodo(inicio="2022-07", fim="2023-06")
        atual = Periodo(inicio="2025-07", fim="2026-06")
        assert dashboard.kpis(SqliteRepository(path), base, atual, filtros, indicador="inadimplencia") == dashboard.kpis(mock, base, atual, filtros, indicador="inadimplencia")
