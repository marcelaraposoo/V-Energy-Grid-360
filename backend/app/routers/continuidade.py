from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import COMP, repo_dep
from app.schemas import AlimentadorDecFec, Periodo
from app.services import continuidade

router = APIRouter(prefix="/api/continuidade", tags=["continuidade (DEC/FEC)"])


def _periodo(repo, inicio, fim) -> Periodo:
    c = repo.competencias()
    return Periodo(inicio=inicio or c[-12], fim=fim or c[-1])


@router.get("/alimentadores", response_model=list[AlimentadorDecFec])
def ranking(inicio: str | None = Query(None, pattern=COMP), fim: str | None = Query(None, pattern=COMP),
            municipio: str | None = None, repo=Depends(repo_dep)):
    return continuidade.ranking_alimentadores(repo, _periodo(repo, inicio, fim), municipio)


@router.get("/alimentadores/{alimentador_id}/serie")
def serie(alimentador_id: str, inicio: str | None = Query(None, pattern=COMP), fim: str | None = Query(None, pattern=COMP),
          repo=Depends(repo_dep)):
    c = repo.competencias()
    s = continuidade.serie_mensal(repo, alimentador_id, Periodo(inicio=inicio or c[0], fim=fim or c[-1]))
    if not s:
        raise HTTPException(404, f"Alimentador {alimentador_id} não encontrado")
    return s
