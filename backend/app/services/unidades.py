from __future__ import annotations

from decimal import Decimal

from app.core.errors import NaoEncontrado
from app.schemas import (
    COMPARACAO_CONTA_ALTA_PADRAO,
    ClassificacaoVariacao,
    ComparacaoMetricaUC,
    DiagnosticoContaAltaUC,
    TipoComparacaoContaAlta,
    Visao360,
)
from app.services.continuidade import dec_fec

LIMITE_VARIACAO_PEQUENA_PCT = 5.0
LIMITE_VARIACAO_MODERADA_PCT = 15.0


def _mes_anterior(competencia: str, meses: int) -> str:
    ano, mes = map(int, competencia.split("-"))
    ano, mes = divmod(ano * 12 + mes - 1 - meses, 12)
    return f"{ano:04d}-{mes + 1:02d}"


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
        mensagem = f"{nome}: não há competências disponíveis na base."
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
    competencias: list[str], serie: list[dict], faturas: list[dict],
    comparacao: TipoComparacaoContaAlta,
) -> DiagnosticoContaAltaUC:
    atuais = []
    referencia = []
    if competencias:
        ultima = competencias[-1]
        if comparacao == "mes_anterior":
            atuais, referencia = [ultima], [_mes_anterior(ultima, 1)]
        elif comparacao == "ano_anterior":
            atuais, referencia = [ultima], [_mes_anterior(ultima, 12)]
        else:
            atuais = [_mes_anterior(ultima, meses) for meses in (2, 1, 0)]
            referencia = [_mes_anterior(c, 12) for c in atuais]

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
        comparacao=comparacao, competencias_atuais=atuais, competencias_referencia=referencia,
        consumo=consumo, faturamento=faturamento, mensagem=mensagem,
    )


def visao_360(
    repo, uc_id: str, comparacao: TipoComparacaoContaAlta = COMPARACAO_CONTA_ALTA_PADRAO,
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
    diag = _diagnostico_conta_alta(c, serie, faturas, comparacao)
    oc = repo.ocorrencias(c[max(0, len(c) - 12)], c[-1], alimentador_id=uc["alimentador_id"]) if c else []
    alim = next(a for a in repo.alimentadores() if a["id"] == uc["alimentador_id"])
    dec, fec = dec_fec(oc, alim["ucs_total"])
    return Visao360(
        cadastro=uc, consumo=consumo, diagnostico_conta_alta=diag, faturas=faturas[:12],
        faturas_em_aberto=[f for f in faturas if f["status"] in ("aberta", "atrasada")],
        medidor=repo.medidor_uc(uc_id), geracao_distribuida=repo.gd_uc(uc_id),
        interrupcoes={"alimentador_id": uc["alimentador_id"], "ultimos_12_meses": len(oc), "dec_horas": dec,
                      "fec_vezes": fec, "recentes": sorted(oc, key=lambda o: o["data"], reverse=True)[:5]},
        atendimentos=sorted(repo.atendimentos_uc(uc_id), key=lambda a: a["data"], reverse=True),
    )
