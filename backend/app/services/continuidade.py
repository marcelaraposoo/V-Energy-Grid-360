"""DEC = Σ(UCs afetadas × duração_h) / UCs do conjunto ; FEC = Σ(UCs afetadas) / UCs do conjunto.
Simplificado (vide enunciado): serve para comparar alimentadores/períodos, não para limites da ANEEL."""
from __future__ import annotations

from collections import defaultdict

from app.schemas import AlimentadorDecFec, Periodo


def dec_fec(ocorrencias: list[dict], ucs_total: int) -> tuple[float, float]:
    if not ucs_total:
        return 0.0, 0.0
    dec = sum(o["ucs_afetadas"] * o["duracao_h"] for o in ocorrencias) / ucs_total
    fec = sum(o["ucs_afetadas"] for o in ocorrencias) / ucs_total
    return round(dec, 3), round(fec, 3)


def ranking_alimentadores(repo, periodo: Periodo, municipio: str | None = None) -> list[AlimentadorDecFec]:
    por_alim: dict[str, list[dict]] = defaultdict(list)
    for o in repo.ocorrencias(periodo.inicio, periodo.fim, municipio=municipio):
        por_alim[o["alimentador_id"]].append(o)
    linhas = []
    for a in repo.alimentadores(municipio):
        oc = por_alim.get(a["id"], [])
        dec, fec = dec_fec(oc, a["ucs_total"])
        linhas.append((a, dec, fec, len(oc)))
    linhas.sort(key=lambda x: x[1], reverse=True)
    return [
        AlimentadorDecFec(alimentador_id=a["id"], municipio=a["municipio"], dec_horas=dec, fec_vezes=fec,
                          n_ocorrencias=n, posicao_pior=i + 1)
        for i, (a, dec, fec, n) in enumerate(linhas)
    ]


def serie_mensal(repo, alimentador_id: str, periodo: Periodo) -> list[dict]:
    alim = next((a for a in repo.alimentadores() if a["id"] == alimentador_id), None)
    if not alim:
        return []
    por_comp: dict[str, list[dict]] = defaultdict(list)
    for o in repo.ocorrencias(periodo.inicio, periodo.fim, alimentador_id=alimentador_id):
        por_comp[o["competencia"]].append(o)
    out = []
    for c in repo.competencias():
        if periodo.inicio <= c <= periodo.fim:
            dec, fec = dec_fec(por_comp.get(c, []), alim["ucs_total"])
            out.append({"competencia": c, "dec_horas": dec, "fec_vezes": fec})
    return out
