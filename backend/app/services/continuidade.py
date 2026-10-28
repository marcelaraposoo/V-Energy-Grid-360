"""Indicadores da A8, calculados por alimentador e competência.

Períodos acumulam os índices mensais, respeitando a base de UCs de cada mês.
OSCILACAO permanece incluída conforme a premissa registrada em docs/contrato-gold.md.
"""
from __future__ import annotations

from collections import defaultdict

from app.schemas import AlimentadorDecFec, Periodo


def resumo_periodo(indicadores: list[dict]) -> dict:
    por_mes = defaultdict(list)
    for linha in indicadores:
        por_mes[linha["mes_referencia"]].append(linha)
    dec, fec = 0.0, 0.0
    for linhas in por_mes.values():
        qtd_ucs = sum(r["qtd_ucs_alimentador_mes"] for r in linhas)
        if qtd_ucs:
            dec += sum(r["horas_interrompidas"] for r in linhas) / qtd_ucs
            fec += sum(r["qtd_interrupcoes"] for r in linhas) / qtd_ucs
    ultimo_mes = max(por_mes, default=None)
    return {
        "dec_horas": round(dec, 6), "fec_vezes": round(fec, 6),
        "n_ocorrencias": sum(r["qtd_interrupcoes"] for r in indicadores),
        "horas_interrompidas": sum(r["horas_interrompidas"] for r in indicadores),
        "qtd_ucs_alimentador_mes": sum(r["qtd_ucs_alimentador_mes"] for r in por_mes[ultimo_mes]) if ultimo_mes else None,
        "competencia_base_ucs": ultimo_mes,
    }


def ranking_alimentadores(repo, periodo: Periodo, municipio: str | None = None) -> list[AlimentadorDecFec]:
    por_alim = defaultdict(list)
    for r in repo.indicadores_continuidade(periodo.inicio, periodo.fim, municipio=municipio):
        por_alim[r["alimentador"]].append(r)
    linhas = [
        {"alimentador_id": a["id"], "municipio": a["municipio"], **resumo_periodo(por_alim[a["id"]])}
        for a in repo.alimentadores(municipio)
    ]
    linhas.sort(key=lambda r: (-r["dec_horas"], r["alimentador_id"]))
    return [AlimentadorDecFec(**r, posicao_pior=i + 1) for i, r in enumerate(linhas)]


def serie_mensal(repo, alimentador_id: str, periodo: Periodo) -> list[dict]:
    return [
        {**r, "competencia": r["mes_referencia"], "fec_vezes": r["fec"]}
        for r in repo.indicadores_continuidade(periodo.inicio, periodo.fim, alimentador_id=alimentador_id)
    ]
