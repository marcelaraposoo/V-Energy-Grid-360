"""Insights da Visão 360: interpretam os números da UC em vez de repeti-los.

Cada regra só entra quando se aplica à UC: por que a conta mudou (consumo × preço), se o consumo está
no padrão (sazonalidade), troca de medidor e interrupções. Os números saem da Gold; a IA, quando ligada,
só reescreve o texto.
"""
from app.schemas import Insight, Visao360

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
LIMITE_VARIACAO = 10    # abaixo disso (em %), o consumo está "em linha" com a média
LIMITE_SAZONAL = 15     # diferença máxima (em pontos) entre as variações dos dois anos para ser "sazonal"


def _br(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(variacao: float) -> str:
    return f"{_br(abs(variacao), 1)}%"


def _mes(competencia: str | None) -> str:
    """'2026-06' → 'jun/2026'."""
    if not competencia:
        return "o mês de referência"
    ano, mes = competencia.split("-")
    return f"{_MESES[int(mes) - 1]}/{ano}"


def _deslocar(competencia: str, meses: int) -> str:
    indice = int(competencia[:4]) * 12 + int(competencia[5:7]) - 1 + meses
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _variacao(atual: float | None, base: float | None) -> float | None:
    return (atual / base - 1) * 100 if atual is not None and base else None


def _meses(**competencias: str | None) -> dict:
    """Meses citados no texto também vão nos dados: a reescrita só pode citar o que está neles
    (e confere os anos como números). Sem isso, ela tira os meses ou recusa a frase."""
    dados = {}
    for chave, competencia in competencias.items():
        if competencia:
            dados[f"mes_{chave}"] = _mes(competencia)
            dados[f"ano_{chave}"] = int(competencia[:4])
    return dados


def _consumo(fatura: dict | None) -> float | None:
    return fatura.get("consumo_kwh") if fatura else None


def _media_6_meses(por_mes: dict[str, dict], competencia: str) -> float | None:
    """Média do consumo nos 6 meses antes da competência; com menos de 3 faturas, sem média."""
    valores = [c for n in range(1, 7) if (c := _consumo(por_mes.get(_deslocar(competencia, -n)))) is not None]
    return sum(valores) / len(valores) if len(valores) >= 3 else None


def _nome_bandeira(bandeira: str) -> str:
    return bandeira.replace("Vermelha", "vermelha").replace("Amarela", "amarela").replace("Verde", "verde")


def _decomposicao(atual: dict | None, ref: dict | None, mes_atual: str, mes_ref: str, meses: dict) -> Insight | None:
    """Por que a conta mudou (P5): a variação da energia separada em consumo e preço do kWh, como na
    Análise de Receita (efeito consumo = Δkwh × preço de referência; efeito preço = o restante)."""
    if not atual or not ref or not atual.get("consumo_kwh") or not ref.get("consumo_kwh"):
        return None
    if atual.get("valor_energia") is None or ref.get("valor_energia") is None:
        return None
    preco_ref = ref["valor_energia"] / ref["consumo_kwh"]
    preco_atual = atual["valor_energia"] / atual["consumo_kwh"]
    variacao = atual["valor_energia"] - ref["valor_energia"]
    efeito_consumo = (atual["consumo_kwh"] - ref["consumo_kwh"]) * preco_ref
    efeito_preco = variacao - efeito_consumo
    if round(variacao, 2) == 0:
        return None

    def parte(valor: float, sujeito_maior: str, sujeito_menor: str, igual: str) -> str:
        if round(valor, 2) == 0:
            return igual
        return f"{sujeito_maior if valor > 0 else sujeito_menor} {'somou' if valor > 0 else 'reduziu'} R$ {_br(abs(valor), 2)}"

    texto = (
        f"A energia da conta {'subiu' if variacao > 0 else 'caiu'} R$ {_br(abs(variacao), 2)} em relação a {mes_ref}: "
        f"{parte(efeito_consumo, 'o consumo maior', 'o consumo menor', 'o consumo não mudou')} e "
        f"{parte(efeito_preco, 'o preço mais alto do kWh', 'o preço mais baixo do kWh', 'o preço do kWh não mudou')}"
    )
    bandeira, bandeira_ref = atual.get("bandeira"), ref.get("bandeira")
    if bandeira and bandeira_ref and bandeira != bandeira_ref:
        texto += f" (bandeira {_nome_bandeira(bandeira)} em {mes_atual}, contra {_nome_bandeira(bandeira_ref)} em {mes_ref})"

    if variacao > 0 and efeito_preco > 0 and efeito_preco >= abs(efeito_consumo):
        tipo = "destaque"  # a alta veio do preço, não do consumo: a resposta típica ao "a conta veio alta"
    elif variacao > 0 and (_variacao(atual["valor_energia"], ref["valor_energia"]) or 0) >= LIMITE_VARIACAO:
        tipo = "alerta"
    else:
        tipo = "informativo"
    return Insight(
        tipo=tipo,
        dados={
            "energia_atual": round(atual["valor_energia"], 2), "energia_referencia": round(ref["valor_energia"], 2),
            "variacao_energia": round(variacao, 2), "efeito_consumo": round(efeito_consumo, 2), "efeito_preco": round(efeito_preco, 2),
            "consumo_atual_kwh": atual["consumo_kwh"], "consumo_referencia_kwh": ref["consumo_kwh"],
            "preco_atual_kwh": round(preco_atual, 4), "preco_referencia_kwh": round(preco_ref, 4),
            "bandeira_atual": bandeira, "bandeira_referencia": bandeira_ref, **meses,
        },
        texto=texto + ".",
    )


def _sazonalidade(por_mes: dict[str, dict], atual: str, ref: str | None, mes_atual: str, mes_ref: str, meses: dict) -> Insight | None:
    """O consumo do mês está no padrão? Compara com a média dos 6 meses anteriores e, se a referência é o
    mesmo mês do ano anterior, com a variação que ele teve: parecida = sazonal; diferente = fora do padrão."""
    consumo, media = _consumo(por_mes.get(atual)), _media_6_meses(por_mes, atual)
    variacao = _variacao(consumo, media)
    if variacao is None:
        return None
    dados = {"consumo_atual_kwh": consumo, "consumo_medio_6m_kwh": round(media, 2), "variacao_6m_pct": round(variacao, 2), **meses}
    if abs(variacao) < LIMITE_VARIACAO:
        return Insight(tipo="informativo", dados=dados,
                       texto=f"O consumo de {mes_atual} está em linha com a média dos 6 meses anteriores ({_br(media)} kWh).")

    texto = f"O consumo de {mes_atual} ficou {_pct(variacao)} {'acima' if variacao > 0 else 'abaixo'} da média dos 6 meses anteriores ({_br(media)} kWh)"
    variacao_ref = None
    if ref and ref == _deslocar(atual, -12):
        variacao_ref = _variacao(_consumo(por_mes.get(ref)), _media_6_meses(por_mes, ref))
    if variacao_ref is None:
        return Insight(tipo="alerta" if variacao >= 20 else "informativo", dados=dados, texto=texto + ".")

    dados |= {"variacao_6m_referencia_pct": round(variacao_ref, 2)}
    lado_ref = "acima" if variacao_ref > 0 else "abaixo"
    if (variacao > 0) == (variacao_ref > 0) and abs(variacao - variacao_ref) <= LIMITE_SAZONAL:
        return Insight(tipo="informativo", dados=dados,
                       texto=f"{texto}, mas o padrão é sazonal: em {mes_ref}, ficou {_pct(variacao_ref)} {lado_ref}.")
    return Insight(tipo="alerta" if variacao > 0 else "destaque", dados=dados,
                   texto=f"{texto}, fora do padrão do ano anterior (em {mes_ref}, ficou {_pct(variacao_ref)} {lado_ref}).")


def insights_uc(visao: Visao360, faturas: list[dict] | None = None) -> list[Insight]:
    """Até 4 leituras da UC, só as que se aplicam. A referência é a pedida pela tela (o mesmo mês do ano
    anterior) e `faturas` é o histórico da UC; sem ele, ficam só troca de medidor e interrupções."""
    diag = visao.diagnostico_conta_alta
    atual, ref = diag.competencia_atual, diag.competencia_referencia
    mes_atual, mes_ref = _mes(atual), _mes(ref)
    meses = _meses(atual=atual, referencia=ref)
    por_mes = {f["competencia"]: f for f in faturas or []}
    result = [
        _decomposicao(por_mes.get(atual), por_mes.get(ref), mes_atual, mes_ref, meses) if atual else None,
        _sazonalidade(por_mes, atual, ref, mes_atual, mes_ref, meses) if atual else None,
    ]

    trocas = [m for m, houve in ((ref, diag.troca_medidor_referencia), (atual, diag.troca_medidor_atual)) if houve and m]
    if trocas:
        result.append(Insight(
            tipo="informativo",
            dados={"troca_medidor_atual": bool(diag.troca_medidor_atual), "troca_medidor_referencia": bool(diag.troca_medidor_referencia), **meses},
            texto=f"Houve troca de medidor em {' e '.join(_mes(m) for m in trocas)}: no mês da troca, o consumo usa a leitura do medidor novo.",
        ))

    i = visao.interrupcoes
    if i.qtd_ocorrencias > 0:
        horas = i.duracao_total_min / 60
        periodo = f"Entre {_mes(i.periodo_inicio)} e {_mes(i.periodo_fim)}" if i.periodo_inicio and i.periodo_fim else "No período"
        result.append(Insight(
            tipo="alerta",
            dados={"qtd_ocorrencias": i.qtd_ocorrencias, "duracao_total_min": i.duracao_total_min,
                   "duracao_total_horas": round(horas, 1), **_meses(inicio=i.periodo_inicio, fim=i.periodo_fim)},
            texto=(f"{periodo}, a UC teve {_br(i.qtd_ocorrencias)} {'interrupção' if i.qtd_ocorrencias == 1 else 'interrupções'}, "
                   f"somando {_br(horas, 1)} horas sem energia."),
        ))
    return [insight for insight in result if insight is not None]
