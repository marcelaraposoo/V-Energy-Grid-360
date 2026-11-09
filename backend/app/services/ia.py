"""Integração HTTP do assistente Text-to-SQL e composição da resposta de auditoria."""
from __future__ import annotations

import asyncio
import logging

from app.schemas import AuditoriaIa, Filtros, Insight, RespostaOut
from app.agent.guardrails.allowed_tables import ALLOWED_TABLES
from sqlglot import exp, parse_one
from app.services import continuidade, dashboard, perdas, receita

logger = logging.getLogger(__name__)


def _fontes_documentais(resultado):
    from app.agent.context.knowledge import source_labels
    return source_labels(getattr(resultado, "source_ids", ()))


def _fontes_da_consulta(sql: str | None) -> list[str]:
    """Extrai somente tabelas autorizadas presentes no SQL validado."""
    if not sql:
        return []
    try:
        expression = parse_one(sql, read="sqlite")
        cte_names = {
            cte.alias_or_name.lower()
            for cte in expression.find_all(exp.CTE)
            if cte.alias_or_name
        }
        return sorted({
            table.name.lower()
            for table in expression.find_all(exp.Table)
            if table.name
            and table.name.lower() in ALLOWED_TABLES
            and table.name.lower() not in cte_names
        })
    except Exception:
        # A falha de parsing não deve impedir a resposta já aprovada.
        return []


def _auditoria_da_resposta(resultado) -> AuditoriaIa:
    if resultado.audit_persisted is True:
        persistencia = "salva"
    elif resultado.audit_persisted is False:
        persistencia = "falha"
    else:
        persistencia = "indisponivel"

    return AuditoriaIa(
        request_id=resultado.request_id,
        resultado=(resultado.outcome.value if resultado.outcome else resultado.status.value),
        etapa_final=resultado.stage.value,
        duracao_ms=resultado.duration_ms,
        cache_hit=resultado.cache_hit,
        regeneracoes=getattr(resultado, "regenerations", 0),
        linhas_retornadas=resultado.row_count,
        resultado_truncado=resultado.truncated,
        persistencia=persistencia,
        etapas=[
            {
                "codigo": etapa.code,
                "nome": etapa.name,
                "status": etapa.status.value,
                "detalhe": etapa.detail,
                "duracao_ms": etapa.duration_ms,
            }
            for etapa in resultado.audit_steps
        ],
        tentativas_provedor=[
            {
                "fase": tentativa.phase.value if tentativa.phase else None,
                "provedor": tentativa.provider.value,
                "modelo": tentativa.model,
                "tentativa": tentativa.attempt,
                "iniciada_em": tentativa.started_at,
                "sucesso": tentativa.success,
                "latencia_ms": tentativa.latency_ms,
                "tipo_erro": tentativa.error_type.value if tentativa.error_type else None,
            }
            for tentativa in resultado.provider_attempts
        ],
    )


def perguntar(pergunta: str, sessao_id: str | None = None) -> RespostaOut:
    from app.agent.pipeline import PipelineStatus, answer_question

    resultado = asyncio.run(answer_question(pergunta, session_id=sessao_id))
    auditoria = _auditoria_da_resposta(resultado)

    if resultado.status == PipelineStatus.ANSWERED:
        logger.info("Pergunta respondida. request_id=%s", resultado.request_id)
        return RespostaOut(
            status="ok",
            resposta=resultado.message,
            sql_executado=resultado.sql,
            fontes=_fontes_da_consulta(resultado.sql) + _fontes_documentais(resultado),
            visualizacao=(
                resultado.visualization.model_dump(mode="json")
                if resultado.visualization
                else None
            ),
            auditoria=auditoria,
        )

    return RespostaOut(
        status="nao_sei",
        resposta=resultado.message,
        sql_executado=None,
        fontes=[],
        auditoria=auditoria,
    )


def limpar_sessao(sessao_id: str) -> None:
    """STUB. Quando existir agent/memory.py, apagar aqui o histórico da sessão."""
    return None


def _insights_base(repo, tela: str) -> list[Insight]:
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
    if tela == "perdas":
        return perdas.insights_fila(repo)
    if tela == "continuidade":
        r = continuidade.ranking_alimentadores(repo, atual)
        return [Insight(tipo="alerta", dados=r[0].model_dump(),
                        texto=f"O alimentador {r[0].alimentador_id} ({r[0].municipio}) tem o pior DEC do período: {r[0].dec_horas} h.")]
    return []


from app.agent.insights.rewriter import rewrite_insights


def insights(repo, tela: str) -> list[Insight]:
    return rewrite_insights(_insights_base(repo, tela))
