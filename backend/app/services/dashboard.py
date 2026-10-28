from __future__ import annotations

from app.schemas import Filtros, Kpi, KpisResponse, Periodo, SeriePonto
from app.services.continuidade import resumo_periodo


def periodos_padrao(repo) -> tuple[Periodo, Periodo]:
    """Padrão do case: últimos 12 meses (atual) vs primeiros 12 meses da base (base)."""
    c = repo.competencias()
    return Periodo(inicio=c[0], fim=c[11]), Periodo(inicio=c[-12], fim=c[-1])


def _kpi(nome, unidade, atual, base) -> Kpi:
    return Kpi(nome=nome, unidade=unidade, valor_atual=round(atual, 2), valor_base=round(base, 2),
               variacao_abs=round(atual - base, 2), variacao_pct=round((atual / base - 1) * 100, 2) if base else None)


def _calc(repo, p: Periodo, f: Filtros) -> dict:
    rows = repo.faturas(p.inicio, p.fim, f.municipio, f.bairro, f.classe)
    receita = sum(r["valor"] for r in rows)
    kwh = sum(r["consumo_kwh"] for r in rows)
    atrasado = sum(r["valor"] for r in rows if r["status"] == "atrasada")
    continuidade = resumo_periodo(repo.indicadores_continuidade(p.inicio, p.fim, municipio=f.municipio))
    return {
        "receita": receita, "kwh": kwh, "tarifa": receita / kwh if kwh else 0,
        "ucs": len({r["uc_id"] for r in rows}), "inadimplencia": atrasado / receita * 100 if receita else 0,
        "dec": continuidade["dec_horas"], "fec": continuidade["fec_vezes"],
    }


def kpis(repo, base: Periodo, atual: Periodo, f: Filtros) -> KpisResponse:
    b, a = _calc(repo, base, f), _calc(repo, atual, f)
    return KpisResponse(periodo_base=base, periodo_atual=atual, kpis=[
        _kpi("Receita faturada", "R$", a["receita"], b["receita"]),
        _kpi("Energia faturada", "kWh", a["kwh"], b["kwh"]),
        _kpi("Tarifa média efetiva", "R$/kWh", a["tarifa"], b["tarifa"]),
        _kpi("UCs faturadas", "UCs", a["ucs"], b["ucs"]),
        _kpi("Inadimplência", "%", a["inadimplencia"], b["inadimplencia"]),
        _kpi("DEC (simplificado)", "h", a["dec"], b["dec"]),
        _kpi("FEC (simplificado)", "vezes", a["fec"], b["fec"]),
    ])


def serie(repo, f: Filtros) -> list[SeriePonto]:
    comps = repo.competencias()
    acc = {c: [0.0, 0.0] for c in comps}
    for r in repo.faturas(comps[0], comps[-1], f.municipio, f.bairro, f.classe):
        acc[r["competencia"]][0] += r["consumo_kwh"]
        acc[r["competencia"]][1] += r["valor"]
    return [SeriePonto(competencia=c, receita=round(v[1], 2), energia_kwh=round(v[0], 1),
                       tarifa_media=round(v[1] / v[0], 4) if v[0] else 0) for c, v in acc.items()]
