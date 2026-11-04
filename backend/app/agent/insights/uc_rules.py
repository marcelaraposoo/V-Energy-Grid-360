from app.schemas import Insight, Visao360


def _br(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def insights_uc(visao: Visao360) -> list[Insight]:
    diag = visao.diagnostico_conta_alta
    result: list[Insight] = []

    c = diag.consumo
    if c.variacao_pct is not None and c.valor_atual is not None:
        tipo = "alerta" if c.variacao_pct >= 10 else "informativo"
        result.append(Insight(
            tipo=tipo,
            dados={
                "consumo_atual_kwh": c.valor_atual,
                "consumo_referencia_kwh": c.valor_referencia,
                "variacao_consumo_pct": c.variacao_pct,
            },
            texto=(
                f"O consumo foi de {_br(c.valor_atual)} kWh, "
                f"{_br(c.variacao_pct, 1)}% em relação ao mês de referência."
            ),
        ))

    f = diag.faturamento
    if f.variacao_pct is not None and f.valor_atual is not None:
        result.append(Insight(
            tipo="informativo",
            dados={
                "valor_atual": f.valor_atual,
                "valor_referencia": f.valor_referencia,
                "variacao_valor_pct": f.variacao_pct,
            },
            texto=(
                f"A fatura foi de R$ {_br(f.valor_atual, 2)}, "
                f"{_br(f.variacao_pct, 1)}% em relação ao mês de referência."
            ),
        ))

    i = visao.interrupcoes
    if i.qtd_ocorrencias > 0:
        result.append(Insight(
            tipo="alerta",
            dados={
                "qtd_ocorrencias": i.qtd_ocorrencias,
                "duracao_total_min": i.duracao_total_min,
            },
            texto=(
                f"A UC teve {i.qtd_ocorrencias} interrupções no período, "
                f"somando {i.duracao_total_min} minutos."
            ),
        ))

    return result