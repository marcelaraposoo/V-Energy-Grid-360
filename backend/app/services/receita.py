"""Decomposição preço x volume.

ΔReceita = efeito_volume + efeito_preco, com P = receita/kWh (tarifa média efetiva):
  efeito_volume = (Q_atual - Q_base) * P_base
  efeito_preco  = (P_atual - P_base) * Q_atual
A soma é exata. "Preço" inclui reajuste, bandeira e mix de classes (efeito de composição).
"""
from __future__ import annotations

from collections import defaultdict

from app.schemas import Filtros, Periodo, VariacaoLinha, VariacaoResponse


def _chave(f: dict, agrupar_por: str) -> str:
    if agrupar_por == "bairro":
        return f"{f['bairro']} - {f['municipio']}"
    return f[agrupar_por]


def _agregar(repo, periodo: Periodo, filtros: Filtros, agrupar_por: str) -> dict[str, list[float]]:
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # [kwh, receita]
    for f in repo.faturas(periodo.inicio, periodo.fim, filtros.municipio, filtros.bairro, filtros.classe):
        a = acc[_chave(f, agrupar_por)]
        a[0] += f["consumo_kwh"]
        a[1] += f["valor"]
    return acc


def _linha(chave: str, q0: float, r0: float, q1: float, r1: float) -> VariacaoLinha:
    p0 = r0 / q0 if q0 else None
    p1 = r1 / q1 if q1 else None
    p0 = p0 if p0 is not None else (p1 or 0.0)
    p1 = p1 if p1 is not None else p0
    return VariacaoLinha(
        chave=chave, receita_base=round(r0, 2), receita_atual=round(r1, 2), variacao_receita=round(r1 - r0, 2),
        efeito_preco=round((p1 - p0) * q1, 2), efeito_volume=round((q1 - q0) * p0, 2),
        energia_base_kwh=round(q0, 1), energia_atual_kwh=round(q1, 1),
        variacao_energia_pct=round((q1 / q0 - 1) * 100, 2) if q0 else None,
    )


def variacao(repo, base: Periodo, atual: Periodo, filtros: Filtros, agrupar_por: str) -> VariacaoResponse:
    a0 = _agregar(repo, base, filtros, agrupar_por)
    a1 = _agregar(repo, atual, filtros, agrupar_por)
    linhas = [
        _linha(k, *(a0.get(k, [0, 0])), *(a1.get(k, [0, 0])))
        for k in sorted(set(a0) | set(a1))
    ]
    linhas.sort(key=lambda l: l.variacao_receita)  # piores primeiro
    q0, r0 = sum(v[0] for v in a0.values()), sum(v[1] for v in a0.values())
    q1, r1 = sum(v[0] for v in a1.values()), sum(v[1] for v in a1.values())
    return VariacaoResponse(
        agrupar_por=agrupar_por, periodo_base=base, periodo_atual=atual,
        total=_linha("TOTAL", q0, r0, q1, r1), linhas=linhas,
    )
