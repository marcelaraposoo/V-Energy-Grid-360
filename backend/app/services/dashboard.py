from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal

from app.repositories.base import Repository
from app.schemas import DetalheInadimplencia, Filtros, Kpi, KpisResponse, Periodo, SeriePonto
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


@dataclass(frozen=True)
class InadimplenciaPeriodo:
    consolidado_pct: Decimal | None
    ultima_competencia_pct: Decimal | None
    competencias_ausentes: tuple[str, ...]


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


def metricas_mensais(
    repo: Repository, periodo: Periodo, filtros: Filtros, *, segmentos: list[dict] | None = None,
) -> dict[str, MetricasMes]:
    """Lê A5 sem recortes e agrega A3 por mês quando existe filtro regional/classe.

    Não completa lacunas, não mistura competências de inadimplência e não faz
    média dos percentuais dos segmentos. Indisponibilidade da Gold é propagada.
    """
    segmentado = any(v is not None for v in (filtros.municipio, filtros.bairro, filtros.classe))
    if segmentado:
        linhas = segmentos if segmentos is not None else repo.segmentos_mensais(
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


def _valor_monetario(valor) -> Decimal | None:
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() and numero >= 0 else None


def calcular_inadimplencia_periodo(
    repo: Repository, periodo: Periodo, filtros: Filtros, *, segmentos: list[dict] | None = None,
) -> InadimplenciaPeriodo:
    """Proporção do faturamento selecionado ainda em aberto no corte da Gold.

    A3 é usada inclusive na visão geral: agrega dinheiro antes de dividir,
    preservando competências, zeros e lacunas. Não consulta atraso das faturas.
    """
    competencias = _competencias_periodo(periodo)
    linhas = segmentos if segmentos is not None else repo.segmentos_mensais(
        periodo.inicio, periodo.fim, filtros.municipio, filtros.bairro, filtros.classe,
    )
    por_mes = defaultdict(list)
    chaves = set()
    for linha in linhas:
        mes = linha["mes_referencia"]
        if mes not in competencias:
            continue
        chave = (mes, linha["municipio"], linha["bairro"], linha["classe"])
        if chave in chaves:
            raise ValueError(f"fato_segmento_mensal possui segmento duplicado: {chave}.")
        chaves.add(chave)
        por_mes[mes].append(linha)
    ausentes = tuple(mes for mes in competencias if mes not in por_mes)
    valores = {
        mes: (
            _somar_valores([_valor_monetario(r.get("valor_em_aberto")) for r in registros]),
            _somar_valores([_valor_monetario(r.get("receita_total")) for r in registros]),
        ) for mes, registros in por_mes.items()
    }

    def taxa(aberto, total):
        if total is None or total <= 0:
            return None
        return _dividir(aberto * 100 if aberto is not None else None, total)

    aberto_final, total_final = valores.get(periodo.fim, (None, None))
    return InadimplenciaPeriodo(
        consolidado_pct=taxa(
            _somar_valores([v[0] for v in valores.values()]),
            _somar_valores([v[1] for v in valores.values()]),
        ) if not ausentes else None,
        ultima_competencia_pct=taxa(aberto_final, total_final),
        competencias_ausentes=ausentes,
    )


def calcular_periodo(
    repo: Repository, periodo: Periodo, filtros: Filtros, *, segmentos: list[dict] | None = None,
) -> IndicadoresPeriodo:
    """Calcula as métricas sem arredondar preços antes das comparações.

    Receita/consumo exigem todas as competências do intervalo. UCs faturadas e
    inadimplência pertencem exatamente ao mês final, sem recuar para outro mês.
    """
    competencias = _competencias_periodo(periodo)
    mensais = metricas_mensais(repo, periodo, filtros, segmentos=segmentos)
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


def periodos_padrao(repo) -> tuple[Periodo, Periodo]:
    """Padrão do case: últimos 12 meses (atual) vs primeiros 12 meses da base (base)."""
    c = repo.competencias()
    return Periodo(inicio=c[0], fim=c[11]), Periodo(inicio=c[-12], fim=c[-1])


def _kpi(nome, unidade, atual, base) -> Kpi:
    return Kpi(nome=nome, unidade=unidade, valor_atual=round(atual, 2), valor_base=round(base, 2) if base is not None else None,
               variacao_abs=round(atual - base, 2) if base is not None else None,
               variacao_pct=round((atual / base - 1) * 100, 2) if base else None)


def _kpi_calculado(nome: str, unidade: str, comparacao: ComparacaoIndicador, casas: int = 2) -> Kpi:
    def valor(numero):
        return float(_arredondar(Decimal(str(numero)), casas)) if numero is not None else None

    return Kpi(
        nome=nome, unidade=unidade,
        valor_atual=valor(comparacao.valor_atual), valor_base=valor(comparacao.valor_base),
        variacao_abs=comparacao.variacao_abs, variacao_pct=comparacao.variacao_pct,
    )


def _inadimplencia_kpi(
    repo, base: Periodo | None, atual: Periodo, f: Filtros, *,
    segmentos_atual: list[dict] | None = None, segmentos_base: list[dict] | None = None,
) -> Kpi:
    a = calcular_inadimplencia_periodo(repo, atual, f, segmentos=segmentos_atual)
    b = calcular_inadimplencia_periodo(repo, base, f, segmentos=segmentos_base) if base is not None else None
    comparacao = _comparar_valores(b.consolidado_pct if b else None, a.consolidado_pct, pontos_percentuais=True)

    def percentual(valor):
        return float(_arredondar(valor, 2)) if valor is not None else None

    return Kpi(
        nome="Inadimplência", unidade="%", valor_atual=percentual(a.consolidado_pct),
        valor_base=percentual(b.consolidado_pct) if b else None,
        variacao_abs=None, variacao_pct=None, variacao_pp=comparacao.variacao_pp,
        inadimplencia=DetalheInadimplencia(
            ultima_competencia=atual.fim, ultima_competencia_pct=percentual(a.ultima_competencia_pct),
            competencias_ausentes=list(a.competencias_ausentes),
            competencias_ausentes_base=list(b.competencias_ausentes) if b else None,
            data_corte=DATA_CORTE_GOLD,
        ),
    )


def kpis(repo, base: Periodo | None, atual: Periodo, f: Filtros, indicador: Literal["inadimplencia"] | None = None) -> KpisResponse:
    if indicador == "inadimplencia":
        return KpisResponse(periodo_base=base, periodo_atual=atual, kpis=[_inadimplencia_kpi(repo, base, atual, f)])

    # A3 é necessária para inadimplência e compartilhada com os demais KPIs filtrados.
    segmentos_atual = repo.segmentos_mensais(atual.inicio, atual.fim, f.municipio, f.bairro, f.classe)
    segmentos_base = repo.segmentos_mensais(base.inicio, base.fim, f.municipio, f.bairro, f.classe) if base else None
    inadimplencia = _inadimplencia_kpi(repo, base, atual, f, segmentos_atual=segmentos_atual, segmentos_base=segmentos_base)
    a = calcular_periodo(repo, atual, f, segmentos=segmentos_atual)
    b = calcular_periodo(repo, base, f, segmentos=segmentos_base) if base else None
    comparacoes = comparar_indicadores(b, a) if b else {}
    principais = []
    for campo, nome, unidade, casas in (
        ("receita_energia", "Receita faturada", "R$", 2),
        ("consumo_kwh", "Energia faturada", "kWh", 2),
        ("preco_medio_kwh", "Tarifa média efetiva", "R$/kWh", 4),
        ("qtd_ucs_faturadas", "UCs faturadas", "UCs", 0),
    ):
        comparacao = comparacoes[campo] if b else ComparacaoIndicador(valor_base=None, valor_atual=getattr(a, campo))
        principais.append(_kpi_calculado(nome, unidade, comparacao, casas))

    # DEC/FEC preservam o resumo da A8 por município, sem depender das faturas globais.
    continuidade_atual = resumo_periodo(repo.indicadores_continuidade(atual.inicio, atual.fim, municipio=f.municipio))
    continuidade_base = resumo_periodo(repo.indicadores_continuidade(base.inicio, base.fim, municipio=f.municipio)) if base else defaultdict(lambda: None)
    return KpisResponse(periodo_base=base, periodo_atual=atual, kpis=[*principais,
        inadimplencia,
        _kpi("DEC (simplificado)", "h", continuidade_atual["dec_horas"], continuidade_base["dec_horas"]),
        _kpi("FEC (simplificado)", "vezes", continuidade_atual["fec_vezes"], continuidade_base["fec_vezes"]),
    ])


def serie(repo: Repository, f: Filtros, periodos: tuple[Periodo | None, Periodo] | None = None) -> list[SeriePonto]:
    """Valores mensais A5/A3, sem acumular nem preencher lacunas com zero.

    Sem períodos explícitos, mantém todo o catálogo de competências. Os meses
    reais são ordenados uma única vez, inclusive na comparação entre intervalos.
    """
    if periodos is None:
        competencias = sorted(set(repo.competencias()))
        if not competencias:
            return []
        intervalos = [Periodo(inicio=competencias[0], fim=competencias[-1])]
    else:
        intervalos = [p for p in periodos if p is not None]
        competencias = sorted({mes for p in intervalos for mes in _competencias_periodo(p)})

    mensais = {}
    for periodo in intervalos:
        mensais.update(metricas_mensais(repo, periodo, f))

    def valor(numero: Decimal | None, casas: int) -> float | None:
        return float(_arredondar(numero, casas)) if numero is not None and numero.is_finite() else None

    pontos = []
    for mes in competencias:
        metrica = mensais.get(mes)
        receita = metrica.receita_energia if metrica else None
        consumo = metrica.consumo_kwh if metrica else None
        pontos.append(SeriePonto(
            competencia=mes, receita=valor(receita, 2), energia_kwh=valor(consumo, 2),
            tarifa_media=valor(_dividir(receita, consumo), 4),
        ))
    return pontos
