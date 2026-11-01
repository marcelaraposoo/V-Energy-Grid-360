"""Regras temporais do Dashboard; as mesmas situações são testadas no frontend."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.routers.deps import dashboard_periodos_dep, periodos_dep
from app.schemas import Filtros, Periodo
from app.services import dashboard
from app.services.dashboard_periodos import deslocar_mes, quantidade_meses, sugerir_referencia, validar_periodos

COMPETENCIAS = [deslocar_mes("2022-07", i) for i in range(48)]
CASOS = json.loads((Path(__file__).parent / "fixtures/dashboard_periodos.json").read_text())


def resolver(**params):
    argumentos = dict(comparar=True, base_inicio=None, base_fim=None, atual_inicio=None, atual_fim=None,
                      repo=SimpleNamespace(competencias=lambda: COMPETENCIAS))
    return dashboard_periodos_dep(**(argumentos | params))


@pytest.mark.parametrize("caso", CASOS, ids=lambda caso: caso["nome"])
def test_regras_compartilhadas_com_frontend(caso):
    atual = Periodo(**caso["atual"])
    base = Periodo(**caso["base"]) if caso["base"] else None
    if caso["valido"]:
        validar_periodos(atual, base, COMPETENCIAS)
    else:
        with pytest.raises(ValueError):
            validar_periodos(atual, base, COMPETENCIAS)


def test_duracao_inclusiva_nao_depende_da_quantidade_de_dias():
    assert quantidade_meses(Periodo(inicio="2024-02", fim="2024-02")) == 1
    assert quantidade_meses(Periodo(inicio="2024-12", fim="2025-03")) == 4


@pytest.mark.parametrize(("atual", "base"), [
    (("2026-05", "2026-05"), ("2025-05", "2025-05")),
    (("2023-01", "2023-03"), ("2022-10", "2022-12")),
])
def test_sugestao_usa_a_mesma_ordem_previsivel_do_frontend(atual, base):
    assert sugerir_referencia(Periodo(inicio=atual[0], fim=atual[1]), COMPETENCIAS) == Periodo(inicio=base[0], fim=base[1])


def test_intervalo_posterior_exige_escolha_personalizada():
    atual = Periodo(inicio="2022-07", fim="2022-09")
    assert sugerir_referencia(atual, COMPETENCIAS) is None
    base, _ = resolver(atual_inicio="2022-07", atual_fim="2022-09", base_inicio="2022-10", base_fim="2022-12")
    assert base == Periodo(inicio="2022-10", fim="2022-12")


def test_sem_parametros_mantem_os_periodos_do_case():
    base, atual = resolver()
    assert base == Periodo(inicio="2022-07", fim="2023-06")
    assert atual == Periodo(inicio="2025-07", fim="2026-06")


def test_sem_comparacao_aceita_24_meses_e_nao_resolve_referencia():
    base, atual = resolver(comparar=False, atual_inicio="2024-07", atual_fim="2026-06")
    assert base is None
    assert atual == Periodo(inicio="2024-07", fim="2026-06")


def test_periodo_explicito_sem_referencia_sugere_ano_anterior():
    base, _ = resolver(atual_inicio="2026-05", atual_fim="2026-05")
    assert base == Periodo(inicio="2025-05", fim="2025-05")


@pytest.mark.parametrize("params", [
    {"atual_inicio": "2026-01"}, {"base_fim": "2025-06"},
    {"comparar": False, "base_inicio": "2025-05", "base_fim": "2025-05"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-06", "base_inicio": "2026-03", "base_fim": "2026-06"},
    {"atual_inicio": "2026-01", "atual_fim": "2026-04", "base_inicio": "2025-12", "base_fim": "2026-03"},
    {"comparar": False, "atual_inicio": "2024-06", "atual_fim": "2026-06"},
    {"comparar": False, "atual_inicio": "2022-06", "atual_fim": "2022-07"},
])
def test_dependencia_rejeita_requisicoes_inconsistentes_com_422(params):
    with pytest.raises(HTTPException) as erro:
        resolver(**params)
    assert erro.value.status_code == 422


def test_base_curta_sem_referencia_permite_continuar_sem_comparacao():
    repo = SimpleNamespace(competencias=lambda: [deslocar_mes("2025-01", i) for i in range(12)])
    with pytest.raises(HTTPException, match="comparar=false"):
        resolver(repo=repo, atual_inicio="2025-01", atual_fim="2025-08")
    assert resolver(repo=repo, comparar=False, atual_inicio="2025-01", atual_fim="2025-08")[0] is None


def test_receita_mantem_dependencia_anterior_sem_regras_novas_do_dashboard():
    repo = SimpleNamespace(competencias=lambda: COMPETENCIAS)
    base, atual = periodos_dep(base_inicio="2025-01", base_fim="2025-02", atual_inicio="2025-02", atual_fim="2025-06", repo=repo)
    assert base.fim == atual.inicio  # Recortes sobrepostos e diferentes continuam permitidos nesta outra tela.


def test_kpis_sem_comparacao_nao_consultam_base_nem_retornam_variacoes():
    repo = SimpleNamespace(segmentos_mensais=Mock(return_value=[{
        "mes_referencia": "2026-05", "municipio": "Recife", "bairro": "Centro", "classe": "COMERCIAL",
        "receita_total": 100, "valor_em_aberto": 5,
        "receita_energia": 100, "consumo_kwh": 200, "qtd_ucs_faturadas": 10,
    }]), indicadores_continuidade=Mock(return_value=[]))
    filtros = Filtros(municipio="Recife", bairro="Centro", classe="COMERCIAL")
    atual = Periodo(inicio="2026-05", fim="2026-05")
    resposta = dashboard.kpis(repo, None, atual, filtros).model_dump(mode="json")
    repo.segmentos_mensais.assert_called_once_with("2026-05", "2026-05", "Recife", "Centro", "COMERCIAL")
    assert resposta["periodo_base"] is None
    for kpi in resposta["kpis"]:
        assert kpi["valor_atual"] is not None
        assert kpi["valor_base"] is kpi["variacao_abs"] is kpi["variacao_pct"] is None


def test_serie_sem_comparacao_filtra_principal_e_com_comparacao_usa_so_os_dois_intervalos():
    def faturas(inicio, fim, municipio, bairro, classe):
        assert (municipio, bairro, classe) == ("Recife", "Centro", "RESIDENCIAL")
        return [{"competencia": c, "consumo_kwh": 100, "valor": 50} for c in COMPETENCIAS if inicio <= c <= fim]
    repo = SimpleNamespace(competencias=lambda: COMPETENCIAS, faturas=faturas)
    filtros = Filtros(municipio="Recife", bairro="Centro", classe="RESIDENCIAL")
    atual = Periodo(inicio="2026-05", fim="2026-05")
    assert [r.competencia for r in dashboard.serie(repo, filtros, (None, atual))] == ["2026-05"]
    base = Periodo(inicio="2025-05", fim="2025-05")
    assert [r.competencia for r in dashboard.serie(repo, filtros, (base, atual))] == ["2025-05", "2026-05"]
    assert len(dashboard.serie(repo, filtros)) == 48
