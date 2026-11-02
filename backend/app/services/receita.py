"""Decomposição preço x volume para quaisquer dois períodos, a partir da A3 (fato_segmento_mensal).

ΔReceita = efeito_volume + efeito_preco, com P = receita/kWh (tarifa média efetiva):
  efeito_volume = (Q_atual - Q_base) * P_base
  efeito_preco  = (P_atual - P_base) * Q_atual
A soma é exata. "Preço" inclui reajuste, bandeira e mix de classes (efeito de composição).
Sem volume em um dos períodos, o preço dele fica nulo e toda a variação é volume (regra da A4).

UCs são as faturadas na última competência de cada período: somar os meses contaria a mesma UC várias vezes.
O fator GD compara as MESMAS UCs nos dois períodos (as que têm GD no fim do período atual, regra da A4),
o que exige o grão por UC da A2 (fato_consumo_faturamento): a coluna de GD da A3 muda de grupo a cada mês.
"""
from __future__ import annotations

from collections import defaultdict

from app.schemas import FatoresReceita, Filtros, Periodo, SeriePonto, VariacaoLinha, VariacaoResponse
from app.services.dashboard_periodos import deslocar_mes, quantidade_meses

PERIODOS_DIAGNOSTICO = (Periodo(inicio="2022-07", fim="2023-06"), Periodo(inicio="2025-07", fim="2026-06"))


def _num(valor) -> float:
    return float(valor) if valor is not None else 0.0


def _competencias(periodo: Periodo) -> list[str]:
    return [deslocar_mes(periodo.inicio, i) for i in range(quantidade_meses(periodo))]


def _grupo(r: dict, agrupar_por: str, classes: dict[str, str]) -> tuple[str, dict]:
    if agrupar_por == "municipio":
        return r["municipio"], {"rotulo": r["municipio"], "municipio": r["municipio"], "bairro": None, "classe": None}
    if agrupar_por == "bairro":
        # O mesmo bairro existe em municípios diferentes: a chave é o par.
        return f"{r['bairro']} - {r['municipio']}", {"rotulo": r["bairro"], "municipio": r["municipio"], "bairro": r["bairro"], "classe": None}
    return r["classe"], {"rotulo": classes.get(r["classe"], r["classe"]), "municipio": None, "bairro": None, "classe": r["classe"]}


def _acumular(linhas: list[dict], periodo: Periodo, chave) -> dict[str, list[float]]:
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])  # [kwh, receita, ucs no último mês]
    for r in linhas:
        a = acc[chave(r)]
        a[0] += _num(r["consumo_kwh"])
        a[1] += _num(r["receita_energia"])
        if r["mes_referencia"] == periodo.fim:
            a[2] += int(_num(r["qtd_ucs_faturadas"]))
    return acc


def _somar(acc: dict[str, list[float]]) -> list[float]:
    return [sum(v[i] for v in acc.values()) for i in range(3)]


def _pct(base: float, atual: float) -> float | None:
    return round((atual / base - 1) * 100, 2) if base else None


def _linha(chave: str, meta: dict, base: list[float], atual: list[float]) -> VariacaoLinha:
    (q0, r0, u0), (q1, r1, u1) = base, atual
    p0 = r0 / q0 if q0 else None
    p1 = r1 / q1 if q1 else None
    if p0 is None or p1 is None:
        efeito_volume, efeito_preco = r1 - r0, 0.0
    else:
        efeito_volume, efeito_preco = (q1 - q0) * p0, (p1 - p0) * q1
    return VariacaoLinha(
        chave=chave, **meta,
        receita_base=round(r0, 2), receita_atual=round(r1, 2), variacao_receita=round(r1 - r0, 2), variacao_receita_pct=_pct(r0, r1),
        efeito_preco=round(efeito_preco, 2), efeito_volume=round(efeito_volume, 2),
        energia_base_kwh=round(q0, 1), energia_atual_kwh=round(q1, 1), variacao_energia_pct=_pct(q0, q1),
        preco_base_kwh=round(p0, 6) if p0 is not None else None, preco_atual_kwh=round(p1, 6) if p1 is not None else None,
        qtd_ucs_base=int(u0), qtd_ucs_atual=int(u1),
    )


def _pct_bandeira(linhas: list[dict]) -> float | None:
    faturas = sum(_num(r["qtd_faturas"]) for r in linhas)
    return round(sum(_num(r["qtd_faturas_bandeira_nao_verde"]) for r in linhas) / faturas * 100, 2) if faturas else None


def _fatores(repo, linhas_base: list[dict], linhas_atual: list[dict], base: Periodo, atual: Periodo, filtros: Filtros) -> FatoresReceita:
    gd = repo.gd_mesmas_ucs(base.inicio, base.fim, atual.inicio, atual.fim, filtros.municipio, filtros.bairro, filtros.classe)
    # Sem a A2 exportada, os volumes ficam indisponíveis e a contagem vem da A3 (mesma regra "GD no mês").
    qtd_gd = gd["qtd_ucs"] if gd else int(sum(_num(r["qtd_ucs_com_gd"]) for r in linhas_atual if r["mes_referencia"] == atual.fim))
    return FatoresReceita(
        qtd_ucs_com_gd=qtd_gd,
        energia_ucs_gd_base_kwh=round(gd["energia_base_kwh"], 1) if gd else None,
        energia_ucs_gd_atual_kwh=round(gd["energia_atual_kwh"], 1) if gd else None,
        qtd_trocas_medidor_atual=int(sum(_num(r["qtd_trocas_medidor"]) for r in linhas_atual)),
        pct_faturas_bandeira_nao_verde_base=_pct_bandeira(linhas_base),
        pct_faturas_bandeira_nao_verde_atual=_pct_bandeira(linhas_atual),
    )


def _serie(linhas: list[dict], periodo: Periodo) -> list[SeriePonto]:
    por_mes: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in linhas:
        por_mes[r["mes_referencia"]][0] += _num(r["receita_energia"])
        por_mes[r["mes_referencia"]][1] += _num(r["consumo_kwh"])
    pontos = []
    for mes in _competencias(periodo):
        receita, kwh = por_mes[mes] if mes in por_mes else (None, None)
        pontos.append(SeriePonto(
            competencia=mes, receita=round(receita, 2) if receita is not None else None,
            energia_kwh=round(kwh, 1) if kwh is not None else None,
            tarifa_media=round(receita / kwh, 6) if kwh else None,
        ))
    return pontos


def variacao(repo, base: Periodo, atual: Periodo, filtros: Filtros, agrupar_por: str) -> VariacaoResponse:
    linhas_base = repo.segmentos_mensais(base.inicio, base.fim, filtros.municipio, filtros.bairro, filtros.classe)
    linhas_atual = repo.segmentos_mensais(atual.inicio, atual.fim, filtros.municipio, filtros.bairro, filtros.classe)
    classes = repo.classes()
    metas: dict[str, dict] = {}

    def chave(r: dict) -> str:
        k, meta = _grupo(r, agrupar_por, classes)
        metas.setdefault(k, meta)
        return k

    a0, a1 = _acumular(linhas_base, base, chave), _acumular(linhas_atual, atual, chave)
    vazio = [0.0, 0.0, 0]
    linhas = sorted(
        (_linha(k, metas[k], a0.get(k, vazio), a1.get(k, vazio)) for k in set(a0) | set(a1)),
        key=lambda l: (l.variacao_receita, l.chave),  # piores primeiro
    )
    total_meta = {"rotulo": "Total da seleção", **filtros.model_dump()}
    diagnostico = (base, atual) == PERIODOS_DIAGNOSTICO
    return VariacaoResponse(
        agrupar_por=agrupar_por, periodo_base=base, periodo_atual=atual,
        recorte="diagnostico" if diagnostico else "personalizado",
        total=_linha("TOTAL", total_meta, _somar(a0), _somar(a1)), linhas=linhas,
        fatores=_fatores(repo, linhas_base, linhas_atual, base, atual, filtros),
        serie=[*_serie(linhas_base, base), *_serie(linhas_atual, atual)],
    )
