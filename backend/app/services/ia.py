"""Placeholder do Módulo 3. Quando o agente Text-to-SQL existir, ele entra aqui.
Requisitos do case: só SELECT (conexão read-only), dizer "não sei" quando não houver dado,
expor o SQL executado (auditoria) e ignorar tentativas de prompt injection."""
from __future__ import annotations

from app.schemas import Filtros, Insight, Periodo, RespostaOut
from app.services import continuidade, dashboard, receita


def perguntar(pergunta: str, sessao_id: str | None = None) -> RespostaOut:
    return RespostaOut(
        status="nao_implementado",
        resposta="O agente de IA ainda não foi conectado ao backend. Esta é uma resposta de teste.",
        sql_executado=None, fontes=[],
    )


def insights(repo, tela: str) -> list[Insight]:
    """Insights calculados direto dos dados (fiéis por construção). O LLM só reescreve o texto depois."""
    base, atual = dashboard.periodos_padrao(repo)
    if tela == "receita":
        v = receita.variacao(repo, base, atual, Filtros(), "municipio")
        pior = min(v.linhas, key=lambda l: l.efeito_volume)
        return [
            Insight(tipo="destaque", dados=v.total.model_dump(),
                    texto=f"A receita variou R$ {v.total.variacao_receita:,.0f}: preço contribuiu com R$ {v.total.efeito_preco:,.0f} e volume com R$ {v.total.efeito_volume:,.0f}."),
            Insight(tipo="alerta", dados=pior.model_dump(),
                    texto=f"{pior.chave} teve o pior efeito-volume (R$ {pior.efeito_volume:,.0f}; energia {pior.variacao_energia_pct}%)."),
        ]
    if tela == "continuidade":
        r = continuidade.ranking_alimentadores(repo, atual)
        return [Insight(tipo="alerta", dados=r[0].model_dump(),
                        texto=f"O alimentador {r[0].alimentador_id} ({r[0].municipio}) tem o pior DEC do período: {r[0].dec_horas} h.")]
    return []
