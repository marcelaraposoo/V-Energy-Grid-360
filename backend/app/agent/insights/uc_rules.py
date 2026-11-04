"""Insights da Visão 360: interpretam os números da UC em vez de repeti-los.

Cada regra só entra quando se aplica à UC: por que a conta mudou (consumo × preço), se o consumo está
no padrão (média recente e o mesmo mês do ano anterior), troca de medidor e interrupções. Os números saem da Gold; a IA, quando ligada,
só reescreve o texto.
"""
from app.schemas import Insight, Visao360

_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
LIMITE_VARIACAO = 10    # abaixo disso (em %), o consumo está "em linha" com a média
LIMITE_SAZONAL = 15     # diferença máxima (em pontos) entre as variações dos dois anos para serem "semelhantes"
JANELA_MEDIA = 6        # meses antes da competência que entram na média
LIMITE_EFEITO = 0.05    # efeito menor que 5% do maior não é citado (R$ 0,01 de preço numa alta de R$ 28 é ruído)


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


def _media_6_meses(por_mes: dict[str, dict], competencia: str) -> tuple[float, int] | None:
    """Média do consumo nos 6 meses antes da competência e quantas faturas entraram nela; com menos
    de 3 faturas, sem média."""
    valores = [c for n in range(1, JANELA_MEDIA + 1) if (c := _consumo(por_mes.get(_deslocar(competencia, -n)))) is not None]
    return (sum(valores) / len(valores), len(valores)) if len(valores) >= 3 else None


def _descricao_media(qtd_meses: int) -> str:
    """Com histórico incompleto, o texto diz quantos meses entraram na média."""
    if qtd_meses == JANELA_MEDIA:
        return f"média dos {JANELA_MEDIA} meses anteriores"
    return f"média dos {qtd_meses} meses com fatura entre os {JANELA_MEDIA} anteriores"


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

    # Cada efeito com a causa e o valor: "do consumo menor (R$ 2,50 a menos)".
    efeitos = [
        (round(efeito_consumo, 2), "consumo maior" if efeito_consumo > 0 else "consumo menor"),
        (round(efeito_preco, 2), "kWh mais caro" if efeito_preco > 0 else "kWh mais barato"),
    ]
    efeitos = sorted((e for e in efeitos if e[0] != 0), key=lambda e: -abs(e[0]))
    citados = [e for e in efeitos if abs(e[0]) >= LIMITE_EFEITO * abs(efeitos[0][0])] if efeitos else []

    def com_valor(efeito: tuple[float, str]) -> str:
        return f"{efeito[1]} (R$ {_br(abs(efeito[0]), 2)} a {'mais' if efeito[0] > 0 else 'menos'})"

    mudanca = "alta" if variacao > 0 else "queda"
    if len(citados) == 1:
        explicacao = f"a {mudanca} veio {'toda' if len(efeitos) == 1 else 'quase toda'} do {citados[0][1]}"
    elif (citados[0][0] > 0) == (citados[1][0] > 0):
        explicacao = f"a {mudanca} veio do {com_valor(citados[0])} e do {com_valor(citados[1])}"
    else:
        # Sinais opostos: quem puxou a variação vem primeiro; o outro compensou em parte.
        principal, compensou = sorted(citados, key=lambda e: (e[0] > 0) != (variacao > 0))
        explicacao = f"a {mudanca} veio do {com_valor(principal)}, compensada em parte pelo {com_valor(compensou)}"

    texto = (
        f"O valor da energia na conta de {mes_atual} ficou R$ {_br(abs(variacao), 2)} "
        f"{'maior' if variacao > 0 else 'menor'} que em {mes_ref}: {explicacao}"
    )
    bandeira, bandeira_ref = atual.get("bandeira"), ref.get("bandeira")
    # A bandeira explica o preço: só entra quando o efeito do preço é citado.
    if bandeira and bandeira_ref and bandeira != bandeira_ref and any(e[1].startswith("kWh") for e in citados):
        texto += f", com bandeira {_nome_bandeira(bandeira)} em {mes_atual}, contra {_nome_bandeira(bandeira_ref)} em {mes_ref}"

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
    mesmo mês do ano anterior, com a variação que ele teve: parecida = semelhante ao ano anterior (o que,
    sozinho, não prova sazonalidade); diferente = fora do padrão."""
    consumo, janela = _consumo(por_mes.get(atual)), _media_6_meses(por_mes, atual)
    media, qtd_meses = janela or (None, 0)
    variacao = _variacao(consumo, media)
    if variacao is None:
        return None
    dados = {"consumo_atual_kwh": consumo, "consumo_medio_6m_kwh": round(media, 2), "variacao_6m_pct": round(variacao, 2),
             "meses_na_media": qtd_meses, "janela_media_meses": JANELA_MEDIA, **meses}
    if abs(variacao) < LIMITE_VARIACAO:
        return Insight(tipo="informativo", dados=dados,
                       texto=f"O consumo de {mes_atual} está em linha com a {_descricao_media(qtd_meses)} ({_br(media)} kWh).")

    texto = (f"O consumo de {mes_atual} ficou {_pct(variacao)} {'acima' if variacao > 0 else 'abaixo'} "
             f"da {_descricao_media(qtd_meses)} ({_br(media)} kWh)")
    variacao_ref, janela_ref = None, None
    if ref and ref == _deslocar(atual, -12) and (janela_ref := _media_6_meses(por_mes, ref)):
        variacao_ref = _variacao(_consumo(por_mes.get(ref)), janela_ref[0])
    if variacao_ref is None:
        return Insight(tipo="alerta" if variacao >= 20 else "informativo", dados=dados, texto=texto + ".")

    qtd_ref = janela_ref[1]
    dados |= {"variacao_6m_referencia_pct": round(variacao_ref, 2), "meses_na_media_referencia": qtd_ref}
    # A média do ano anterior também pode ter histórico incompleto: aí o texto diz quantos meses entraram.
    lado_ref = f"{'acima' if variacao_ref > 0 else 'abaixo'}{'' if qtd_ref == JANELA_MEDIA else ' da ' + _descricao_media(qtd_ref)}"
    if (variacao > 0) == (variacao_ref > 0) and abs(variacao - variacao_ref) <= LIMITE_SAZONAL:
        return Insight(tipo="informativo", dados=dados,
                       texto=f"{texto}, comportamento semelhante ao observado no ano anterior (em {mes_ref}, ficou {_pct(variacao_ref)} {lado_ref}).")
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
