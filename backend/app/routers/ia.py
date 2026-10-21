from typing import Literal

from fastapi import APIRouter, Depends, Response

from app.routers.deps import repo_dep
from app.schemas import Insight, PerguntaIn, RespostaOut
from app.services import ia

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
    """Implementado para receita e continuidade. As demais telas devolvem lista vazia por enquanto."""
    return ia.insights(repo, tela)
