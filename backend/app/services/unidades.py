from __future__ import annotations

from decimal import Decimal

from app.core.errors import NaoEncontrado
from app.schemas import (
    ClassificacaoVariacao,
    ComparacaoMetricaUC,
    DiagnosticoContaAltaUC,
    PERIODO_HISTORICO_PADRAO,
    PeriodoHistorico,
    PeriodoHistoricoUC,
    Visao360,
)
from app.services.continuidade import resumo_periodo

LIMITE_VARIACAO_PEQUENA_PCT = 5.0
LIMITE_VARIACAO_MODERADA_PCT = 15.0


def _total_periodo(valores: dict, competencias: list[str]) -> Decimal | None:
    if not competencias or any(valores.get(c) is None for c in competencias):
        return None
    return sum((Decimal(str(valores[c])) for c in competencias), Decimal(0))


def _comparar_metrica(
    nome: str, valores: dict, atuais: list[str], referencia: list[str],
) -> ComparacaoMetricaUC:
    total_atual = _total_periodo(valores, atuais)
    total_referencia = _total_periodo(valores, referencia)
    variacao = None
    classificacao: ClassificacaoVariacao | None = None
    if not atuais:
        mensagem = f"{nome}: não há competências disponíveis no histórico desta UC."
    elif not referencia:
        mensagem = f"{nome}: não há competência anterior com histórico para comparação."
    elif total_atual is None or total_referencia is None:
        ausentes = [c for c in referencia + atuais if valores.get(c) is None]
        mensagem = f"{nome}: dados indisponíveis nas competências {', '.join(ausentes)}."
    elif total_referencia == 0:
        mensagem = f"{nome}: valor de referência igual a zero; variação percentual não calculável."
    else:
        variacao = (total_atual - total_referencia) / total_referencia * 100
        if variacao < 0:
            classificacao = "reducao"
            mensagem = f"{nome}: redução de {abs(variacao):.2f}%."
        else:
            if variacao <= LIMITE_VARIACAO_PEQUENA_PCT:
                classificacao = "pequena"
            elif variacao <= LIMITE_VARIACAO_MODERADA_PCT:
                classificacao = "moderada"
            else:
                classificacao = "significativa"
            mensagem = (
                f"{nome}: sem variação (0%)."
                if variacao == 0 else
                f"{nome}: aumento de {variacao:.2f}% (variação {classificacao})."
            )
    return ComparacaoMetricaUC(
        valor_atual=float(total_atual) if total_atual is not None else None,
        valor_referencia=float(total_referencia) if total_referencia is not None else None,
        variacao_pct=float(variacao) if variacao is not None else None,
        classificacao=classificacao,
        mensagem=mensagem,
    )


def _diagnostico_conta_alta(
    serie: list[dict], faturas: list[dict],
    competencia_atual: str | None, competencia_referencia: str | None,
) -> DiagnosticoContaAltaUC:
    competencias = sorted({s["competencia"] for s in serie} | {f["competencia"] for f in faturas})
    for competencia in (competencia_atual, competencia_referencia):
        if competencia is not None and competencia not in competencias:
            raise ValueError(f"Competência {competencia} sem histórico para esta UC.")
    if competencia_atual is None and competencias:
        competencia_atual = competencias[-1]
    if competencia_referencia is None and competencia_atual is not None:
        anteriores = [c for c in competencias if c < competencia_atual]
        competencia_referencia = anteriores[-1] if anteriores else None
    if competencia_referencia is not None and competencia_referencia >= competencia_atual:
        raise ValueError("O mês de referência deve ser anterior ao mês analisado.")
    atuais = [competencia_atual] if competencia_atual else []
    referencia = [competencia_referencia] if competencia_referencia else []

    consumo = _comparar_metrica(
        "Consumo", {s["competencia"]: s["consumo_kwh"] for s in serie}, atuais, referencia,
    )
    faturamento = _comparar_metrica(
        "Valor cobrado", {f["competencia"]: f.get("valor_total") for f in faturas}, atuais, referencia,
    )
    mensagem = f"{consumo.mensagem} {faturamento.mensagem}"
    vc, vf = consumo.variacao_pct, faturamento.variacao_pct
    if vc is None or vf is None:
        mensagem += " Não é possível relacionar as duas variações com os dados disponíveis."
    elif vf <= 0:
        mensagem += " Não houve aumento do valor cobrado no período."
    elif vc <= 0:
        mensagem += " O aumento da cobrança não foi acompanhado de aumento do consumo."
    elif vf > vc:
        mensagem += " A cobrança aumentou proporcionalmente mais que o consumo."
    elif vf < vc:
        mensagem += " A cobrança aumentou proporcionalmente menos que o consumo."
    else:
        mensagem += " O aumento da cobrança foi acompanhado de aumento do consumo na mesma proporção."
    return DiagnosticoContaAltaUC(
        competencias_disponiveis=competencias,
        competencia_atual=competencia_atual, competencia_referencia=competencia_referencia,
        consumo=consumo, faturamento=faturamento, mensagem=mensagem,
    )


def _periodo_historico(competencias: list[str], periodo: PeriodoHistorico) -> PeriodoHistoricoUC:
    if not competencias:
        return PeriodoHistoricoUC(periodo=periodo, periodo_inicio=None, periodo_fim=None)
    inicio, fim = competencias[0], competencias[-1]
    if periodo != "todos":
        meses = 6 if periodo == "6_meses" else 12
        ano, mes = map(int, fim.split("-"))
        ano, mes = divmod(ano * 12 + mes - meses, 12)
        inicio = max(inicio, f"{ano:04d}-{mes + 1:02d}")
    return PeriodoHistoricoUC(periodo=periodo, periodo_inicio=inicio, periodo_fim=fim)


def visao_360(
    repo, uc_id: str, competencia_atual: str | None = None, competencia_referencia: str | None = None,
    periodo_interrupcoes: PeriodoHistorico = PERIODO_HISTORICO_PADRAO,
    periodo_atendimentos: PeriodoHistorico = PERIODO_HISTORICO_PADRAO,
) -> Visao360:
    uc = repo.uc(uc_id)
    if not uc:
        raise NaoEncontrado(f"Unidade consumidora {uc_id} não encontrada")
    serie = sorted(repo.consumo_uc(uc_id), key=lambda s: s["competencia"])
    por_comp = {s["competencia"]: s["consumo_kwh"] for s in serie}
    ult12 = serie[-12:]
    consumo = []
    for s in ult12:
        ano, mes = s["competencia"].split("-")
        consumo.append({**s, "consumo_kwh_ano_anterior": por_comp.get(f"{int(ano) - 1}-{mes}")})

    faturas = sorted(repo.faturas_uc(uc_id), key=lambda f: f["competencia"], reverse=True)
    c = sorted(repo.competencias())
    diag = _diagnostico_conta_alta(serie, faturas, competencia_atual, competencia_referencia)
    periodo_oc = _periodo_historico(c, periodo_interrupcoes)
    inicio = periodo_oc.periodo_inicio
    oc = repo.ocorrencias(inicio, c[-1], uc_id=uc["uc_id"]) if c else []
    mensais = repo.indicadores_continuidade(inicio, c[-1], alimentador_id=uc["alimentador_id"]) if c else []
    continuidade = resumo_periodo(mensais)
    periodo_at = _periodo_historico(c, periodo_atendimentos)
    atendimentos = [
        a for a in repo.atendimentos_uc(uc_id)
        if c and periodo_at.periodo_inicio <= a["data"][:7] <= periodo_at.periodo_fim
    ]
    return Visao360(
        cadastro=uc, consumo=consumo, diagnostico_conta_alta=diag, faturas=faturas[:12],
        faturas_em_aberto=[f for f in faturas if f["status"] in ("aberta", "atrasada")],
        medidor=repo.medidor_uc(uc_id), geracao_distribuida=repo.gd_uc(uc_id),
        interrupcoes={**periodo_oc.model_dump(), "alimentador_id": uc["alimentador_id"],
                      "qtd_ocorrencias": len(oc), "duracao_total_min": sum(o["duracao_min"] for o in oc),
                      "dec_horas": continuidade["dec_horas"], "fec_vezes": continuidade["fec_vezes"],
                      "escopo": "uc",
                      "historico": sorted(oc, key=lambda o: o["data"], reverse=True)},
        periodo_atendimentos=periodo_at,
        atendimentos=sorted(atendimentos, key=lambda a: a["data"], reverse=True),
    )
