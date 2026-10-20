from fastapi import APIRouter, Depends

from app.routers.deps import repo_dep
from app.schemas import Insight, PerguntaIn, RespostaOut
from app.services import ia

router = APIRouter(prefix="/api/ia", tags=["inteligência artificial"])


@router.post("/perguntar", response_model=RespostaOut)
def perguntar(p: PerguntaIn):
    return ia.perguntar(p.pergunta, p.sessao_id)


@router.get("/insights", response_model=list[Insight])
def insights(tela: str, repo=Depends(repo_dep)):
    return ia.insights(repo, tela)
