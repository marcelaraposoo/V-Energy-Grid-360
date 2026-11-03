"""Indicadores da A8, calculados por alimentador e competência.

Períodos acumulam os índices mensais, respeitando a base de UCs de cada mês.
OSCILACAO permanece incluída conforme a premissa registrada em docs/contrato-gold.md.
"""
from __future__ import annotations

from collections import defaultdict

from app.schemas import (
    AlimentadorDecFec, CausaContinuidade, IndicadoresContinuidade, Periodo, PontoContinuidade, ResumoContinuidade,
)


def resumo_periodo(indicadores: list[dict]) -> dict:
    por_mes = defaultdict(list)
    for linha in indicadores:
        por_mes[linha["mes_referencia"]].append(linha)
    dec, fec = 0.0, 0.0
    for linhas in por_mes.values():
        qtd_ucs = sum(r["qtd_ucs_alimentador_mes"] for r in linhas)
        if qtd_ucs:
            dec += sum(
                r["dec_horas"] * r["qtd_ucs_alimentador_mes"]
                for r in linhas if r["qtd_ucs_alimentador_mes"]
            ) / qtd_ucs
            fec += sum(
                r["fec"] * r["qtd_ucs_alimentador_mes"]
                for r in linhas if r["qtd_ucs_alimentador_mes"]
            ) / qtd_ucs
    ultimo_mes = max(por_mes, default=None)
    return {
        "dec_horas": round(dec, 6), "fec_vezes": round(fec, 6),
        "n_ocorrencias": sum(r["qtd_interrupcoes"] for r in indicadores),
        "horas_interrompidas": sum(r["horas_interrompidas"] for r in indicadores),
        "horas_causas_evitaveis": sum(r.get("horas_causas_evitaveis") or 0 for r in indicadores),
        "qtd_ucs_alimentador_mes": sum(r["qtd_ucs_alimentador_mes"] for r in por_mes[ultimo_mes]) if ultimo_mes else None,
        "competencia_base_ucs": ultimo_mes,
    }


def ranking_alimentadores(repo, periodo: Periodo, municipio: str | None = None) -> list[AlimentadorDecFec]:
    por_alim = defaultdict(list)
    for r in repo.indicadores_continuidade(periodo.inicio, periodo.fim, municipio=municipio):
        por_alim[r["alimentador"]].append(r)
    afetadas = repo.ucs_afetadas_por_alimentador(periodo.inicio, periodo.fim, municipio=municipio)
    linhas = [
        {"alimentador_id": a["id"], "municipio": a["municipio"], **resumo_periodo(por_alim[a["id"]]),
         "qtd_ucs_afetadas": afetadas.get(a["id"], 0)}
        for a in repo.alimentadores(municipio)
    ]
    linhas.sort(key=lambda r: (-r["dec_horas"], r["alimentador_id"]))
    return [AlimentadorDecFec(**r, posicao_pior=i + 1) for i, r in enumerate(linhas)]


def serie_mensal(repo, alimentador_id: str, periodo: Periodo) -> list[dict]:
    return [
        {**r, "competencia": r["mes_referencia"], "fec_vezes": r["fec"]}
        for r in repo.indicadores_continuidade(periodo.inicio, periodo.fim, alimentador_id=alimentador_id)
    ]


def _indicadores(linhas: list[dict]) -> IndicadoresContinuidade | None:
    if not linhas:
        return None
    r = resumo_periodo(linhas)
    return IndicadoresContinuidade(
        dec_horas=r["dec_horas"], fec_vezes=r["fec_vezes"], qtd_interrupcoes=r["n_ocorrencias"],
        horas_interrompidas=round(r["horas_interrompidas"], 6), horas_causas_evitaveis=round(r["horas_causas_evitaveis"], 6),
        qtd_ucs=r["qtd_ucs_alimentador_mes"], competencia_base_ucs=r["competencia_base_ucs"],
    )


def _serie(linhas: list[dict]) -> list[PontoContinuidade]:
    por_mes = defaultdict(list)
    for r in linhas:
        por_mes[r["mes_referencia"]].append(r)
    return [
        PontoContinuidade(competencia=mes, dec_horas=i.dec_horas, fec_vezes=i.fec_vezes,
                          qtd_interrupcoes=i.qtd_interrupcoes, horas_interrompidas=i.horas_interrompidas)
        for mes in sorted(por_mes) if (i := _indicadores(por_mes[mes]))
    ]


def _causas(repo, periodo: Periodo, alimentador_id: str | None, municipio: str | None) -> list[CausaContinuidade]:
    grupos = repo.causas_interrupcao(periodo.inicio, periodo.fim, alimentador_id=alimentador_id, municipio=municipio)
    total = sum(g["minutos"] for g in grupos)
    causas = [
        CausaContinuidade(causa=g["causa"], causa_evitavel=g["causa_evitavel"], qtd_interrupcoes=g["qtd"],
                         horas=round(g["minutos"] / 60, 2), pct_horas=round(100 * g["minutos"] / total, 2) if total else None)
        for g in grupos
    ]
    return sorted(causas, key=lambda c: (-c.horas, c.causa or "~"))


def resumo(repo, atual: Periodo, base: Periodo | None, municipio: str | None = None,
           alimentador_id: str | None = None) -> ResumoContinuidade:
    """Indicadores, série mensal e causas de um recorte (distribuidora, município ou alimentador)."""
    def linhas(p: Periodo) -> list[dict]:
        return repo.indicadores_continuidade(p.inicio, p.fim, alimentador_id=alimentador_id, municipio=municipio)

    atuais = linhas(atual)
    bases = linhas(base) if base else []
    return ResumoContinuidade(
        periodo_atual=atual, periodo_base=base, municipio=municipio, alimentador_id=alimentador_id,
        qtd_alimentadores=len({r["alimentador"] for r in atuais}),
        atual=_indicadores(atuais), base=_indicadores(bases) if base else None,
        serie=_serie(atuais), serie_base=_serie(bases),
        causas=_causas(repo, atual, alimentador_id, municipio),
    )
