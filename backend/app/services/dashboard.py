from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from app.repositories.base import Repository
from app.schemas import Filtros, Kpi, KpisResponse, Periodo, SeriePonto
from app.services.continuidade import resumo_periodo

DATA_CORTE_GOLD = date(2026, 6, 30)


@dataclass(frozen=True)
class MetricasMes:
    """Valores internos da A5 ou do conjunto de segmentos da A3 em um mês.

    Decimal preserva os centavos durante os cálculos; None indica dado ausente
    ou razão indefinida. A conversão para a resposta pública pertence à API.
    """

    receita_energia: Decimal | None
    consumo_kwh: Decimal | None
    qtd_ucs_faturadas: int | None
    inadimplencia_pct: Decimal | None


@dataclass(frozen=True)
class IndicadoresPeriodo:
    """Acumulados do intervalo e posição de UCs/inadimplência na competência final.

    Uma competência ausente invalida os acumulados, mas não a posição final
    quando ela está disponível. A data de corte é a da extração Gold do case.
    """

    periodo: Periodo
    fonte: Literal["kpis_mensal", "fato_segmento_mensal"]
    competencias_ausentes: tuple[str, ...]
    receita_energia: Decimal | None
    consumo_kwh: Decimal | None
    preco_medio_kwh: Decimal | None
    qtd_ucs_faturadas: int | None
    inadimplencia_pct: Decimal | None
    data_corte: date = DATA_CORTE_GOLD

    @property
    def competencia_posicao(self) -> str:
        return self.periodo.fim


@dataclass(frozen=True)
class ComparacaoIndicador:
    valor_base: Decimal | int | None
    valor_atual: Decimal | int | None
    variacao_abs: Decimal | None = None
    variacao_pct: Decimal | None = None
    variacao_pp: Decimal | None = None


def _somar_valores(valores: list[Decimal | int | float | None]) -> Decimal | None:
    if not valores or any(v is None for v in valores):
        return None
    return sum((Decimal(str(v)) for v in valores), Decimal(0))


def _somar_coluna(linhas: list[dict], coluna: str) -> Decimal | None:
    return _somar_valores([r[coluna] for r in linhas])


def _dividir(numerador: Decimal | None, denominador: Decimal | None) -> Decimal | None:
    if numerador is None or denominador is None or denominador == 0:
        return None
    return numerador / denominador


def metricas_mensais(repo: Repository, periodo: Periodo, filtros: Filtros) -> dict[str, MetricasMes]:
    """Lê A5 sem recortes e agrega A3 por mês quando existe filtro regional/classe.

    Não completa lacunas, não mistura competências de inadimplência e não faz
    média dos percentuais dos segmentos. Indisponibilidade da Gold é propagada.
    """
    segmentado = any(v is not None for v in (filtros.municipio, filtros.bairro, filtros.classe))
    if segmentado:
        linhas = repo.segmentos_mensais(
            periodo.inicio, periodo.fim, filtros.municipio, filtros.bairro, filtros.classe,
        )
    else:
        linhas = repo.kpis_mensais(periodo.inicio, periodo.fim)
    por_mes = defaultdict(list)
    for linha in linhas:
        por_mes[linha["mes_referencia"]].append(linha)
    metricas = {}
    for mes, registros in sorted(por_mes.items()):
        if segmentado:
            valor_aberto = _somar_coluna(registros, "valor_em_aberto")
            inadimplencia = _dividir(
                valor_aberto * 100 if valor_aberto is not None else None,
                _somar_coluna(registros, "receita_total"),
            )
        else:
            if len(registros) != 1:
                raise ValueError(f"kpis_mensal possui mais de uma linha para {mes}; o grão da A5 é um mês.")
            # Usa o indicador auditado da Gold, sem reconstruí-lo a partir de uma taxa arredondada.
            taxa = registros[0]["inadimplencia_pct"]
            inadimplencia = Decimal(str(taxa)) if taxa is not None else None
        ucs = _somar_coluna(registros, "qtd_ucs_faturadas")
        metricas[mes] = MetricasMes(
            receita_energia=_somar_coluna(registros, "receita_energia"),
            consumo_kwh=_somar_coluna(registros, "consumo_kwh" if segmentado else "consumo_total_kwh"),
            qtd_ucs_faturadas=int(ucs) if ucs is not None else None,
            inadimplencia_pct=inadimplencia,
        )
    return metricas


def _competencias_periodo(periodo: Periodo) -> tuple[str, ...]:
    inicio = date.fromisoformat(f"{periodo.inicio}-01")
    fim = date.fromisoformat(f"{periodo.fim}-01")
    if inicio > fim:
        raise ValueError("O início do período deve ser anterior ou igual ao fim.")
    primeiro = (inicio.year - 1) * 12 + inicio.month - 1
    ultimo = (fim.year - 1) * 12 + fim.month - 1
    return tuple(f"{i // 12 + 1:04d}-{i % 12 + 1:02d}" for i in range(primeiro, ultimo + 1))


def calcular_periodo(repo: Repository, periodo: Periodo, filtros: Filtros) -> IndicadoresPeriodo:
    """Calcula as métricas sem arredondar preços antes das comparações.

    Receita/consumo exigem todas as competências do intervalo. UCs faturadas e
    inadimplência pertencem exatamente ao mês final, sem recuar para outro mês.
    """
    competencias = _competencias_periodo(periodo)
    mensais = metricas_mensais(repo, periodo, filtros)
    ausentes = tuple(c for c in competencias if c not in mensais)
    meses = [mensais[c] for c in competencias if c in mensais]
    receita = _somar_valores([m.receita_energia for m in meses]) if not ausentes else None
    consumo = _somar_valores([m.consumo_kwh for m in meses]) if not ausentes else None
    posicao = mensais.get(periodo.fim)
    segmentado = any(v is not None for v in (filtros.municipio, filtros.bairro, filtros.classe))
    return IndicadoresPeriodo(
        periodo=periodo,
        fonte="fato_segmento_mensal" if segmentado else "kpis_mensal",
        competencias_ausentes=ausentes,
        receita_energia=receita,
        consumo_kwh=consumo,
        preco_medio_kwh=_dividir(receita, consumo),
        qtd_ucs_faturadas=posicao.qtd_ucs_faturadas if posicao else None,
        inadimplencia_pct=posicao.inadimplencia_pct if posicao else None,
    )


def _arredondar(valor: Decimal, casas: int) -> Decimal:
    return valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def _comparar_valores(
    base: Decimal | int | None,
    atual: Decimal | int | None,
    casas: int = 2,
    *,
    pontos_percentuais: bool = False,
) -> ComparacaoIndicador:
    if base is None or atual is None:
        return ComparacaoIndicador(valor_base=base, valor_atual=atual)
    b, a = Decimal(str(base)), Decimal(str(atual))
    diferenca = a - b
    if pontos_percentuais:
        return ComparacaoIndicador(valor_base=base, valor_atual=atual, variacao_pp=_arredondar(diferenca, 2))
    percentual = _dividir(diferenca * 100, b)
    return ComparacaoIndicador(
        valor_base=base, valor_atual=atual,
        variacao_abs=_arredondar(diferenca, casas),
        variacao_pct=_arredondar(percentual, 2) if percentual is not None else None,
    )


def comparar_indicadores(base: IndicadoresPeriodo, atual: IndicadoresPeriodo) -> dict[str, ComparacaoIndicador]:
    """Referência zero mantém a diferença absoluta e torna o percentual indefinido.

    Inadimplência compara somente as competências finais, em pontos percentuais.
    Ausência de valor em qualquer lado deixa todas as variações indisponíveis.
    """
    return {
        "receita_energia": _comparar_valores(base.receita_energia, atual.receita_energia),
        "consumo_kwh": _comparar_valores(base.consumo_kwh, atual.consumo_kwh),
        "preco_medio_kwh": _comparar_valores(base.preco_medio_kwh, atual.preco_medio_kwh, casas=4),
        "qtd_ucs_faturadas": _comparar_valores(base.qtd_ucs_faturadas, atual.qtd_ucs_faturadas, casas=0),
        "inadimplencia_pct": _comparar_valores(base.inadimplencia_pct, atual.inadimplencia_pct, pontos_percentuais=True),
    }


# As rotas ainda usam os adaptadores abaixo. A migração do contrato HTTP e dos
# tipos compartilhados para os resultados internos acima pertence à etapa 3.
def periodos_padrao(repo) -> tuple[Periodo, Periodo]:
    """Padrão do case: últimos 12 meses (atual) vs primeiros 12 meses da base (base)."""
    c = repo.competencias()
    return Periodo(inicio=c[0], fim=c[11]), Periodo(inicio=c[-12], fim=c[-1])


def _kpi(nome, unidade, atual, base) -> Kpi:
    return Kpi(nome=nome, unidade=unidade, valor_atual=round(atual, 2), valor_base=round(base, 2) if base is not None else None,
               variacao_abs=round(atual - base, 2) if base is not None else None,
               variacao_pct=round((atual / base - 1) * 100, 2) if base else None)


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


def kpis(repo, base: Periodo | None, atual: Periodo, f: Filtros) -> KpisResponse:
    a = _calc(repo, atual, f)
    b = _calc(repo, base, f) if base is not None else defaultdict(lambda: None)
    return KpisResponse(periodo_base=base, periodo_atual=atual, kpis=[
        _kpi("Receita faturada", "R$", a["receita"], b["receita"]),
        _kpi("Energia faturada", "kWh", a["kwh"], b["kwh"]),
        _kpi("Tarifa média efetiva", "R$/kWh", a["tarifa"], b["tarifa"]),
        _kpi("UCs faturadas", "UCs", a["ucs"], b["ucs"]),
        _kpi("Inadimplência", "%", a["inadimplencia"], b["inadimplencia"]),
        _kpi("DEC (simplificado)", "h", a["dec"], b["dec"]),
        _kpi("FEC (simplificado)", "vezes", a["fec"], b["fec"]),
    ])


def serie(repo, f: Filtros, periodos: tuple[Periodo | None, Periodo] | None = None) -> list[SeriePonto]:
    comps = repo.competencias()
    if periodos is not None:
        comps = [c for c in comps if any(p is not None and p.inicio <= c <= p.fim for p in periodos)]
    if not comps:
        return []
    acc = {c: [0.0, 0.0] for c in comps}
    for r in repo.faturas(comps[0], comps[-1], f.municipio, f.bairro, f.classe):
        if r["competencia"] not in acc:
            continue
        acc[r["competencia"]][0] += r["consumo_kwh"]
        acc[r["competencia"]][1] += r["valor"]
    return [SeriePonto(competencia=c, receita=round(v[1], 2), energia_kwh=round(v[0], 1),
                       tarifa_media=round(v[1] / v[0], 4) if v[0] else 0) for c, v in acc.items()]
