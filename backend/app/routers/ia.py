from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from app.agent.insights.rewriter import rewrite_insights
from app.agent.insights.uc_rules import insights_uc
from app.core.errors import NaoDisponivelNaGold
from app.routers.deps import repo_dep
from app.schemas import Insight, PerguntaIn, RespostaOut
from app.services import ia, unidades as unidades_service

router = APIRouter(prefix="/api/ia", tags=["inteligência artificial"])

Tela = Literal["dashboard", "receita", "unidades", "perdas", "continuidade"]


@router.post("/perguntar", response_model=RespostaOut)
def perguntar(p: PerguntaIn):
    """STUB: o agente ainda não está conectado (responde status=nao_implementado)."""
    return ia.perguntar(p.pergunta, p.sessao_id)


@router.delete("/sessoes/{sessao_id}", status_code=204)
def limpar_sessao(sessao_id: str):
    """STUB: encerra a conversa (botão 'nova conversa' do chat). Hoje não faz nada."""
    ia.limpar_sessao(sessao_id)
    return Response(status_code=204)


@router.get("/insights", response_model=list[Insight])
def insights(tela: Tela, repo=Depends(repo_dep)):
    """Implementado para receita, continuidade e perdas. As demais telas devolvem lista vazia por enquanto."""
    return ia.insights(repo, tela)


@router.get("/insights/uc/{uc_id}", response_model=list[Insight])
def insights_da_uc(
    uc_id: str,
    competencia_atual: str | None = None,
    competencia_referencia: str | None = None,
    repo=Depends(repo_dep),
):
    """Insights da Visão 360 de uma UC. Só métricas vão ao modelo."""
    try:
        visao = unidades_service.visao_360(
            repo, uc_id, competencia_atual, competencia_referencia
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        faturas = repo.faturas_uc(uc_id)
    except NaoDisponivelNaGold:
        faturas = []  # sem a A2, ficam só os insights que não dependem do histórico
    return rewrite_insights(insights_uc(visao, faturas))
