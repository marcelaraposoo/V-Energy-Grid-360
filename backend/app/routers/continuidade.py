from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import COMP, repo_dep
from app.schemas import AlimentadorDecFec, Periodo
from app.services import continuidade

router = APIRouter(prefix="/api/continuidade", tags=["continuidade (DEC/FEC)"])


def _periodo(repo, inicio, fim, desde_o_comeco: bool = False) -> Periodo:
    c = repo.competencias()
    p = Periodo(inicio=inicio or (c[0] if desde_o_comeco else c[-12]), fim=fim or c[-1])
    if p.inicio > p.fim:
        raise HTTPException(422, f"Período inválido: início {p.inicio} é maior que o fim {p.fim}")
    return p


@router.get("/alimentadores", response_model=list[AlimentadorDecFec])
def ranking(inicio: str | None = Query(None, pattern=COMP), fim: str | None = Query(None, pattern=COMP),
            municipio: str | None = None, repo=Depends(repo_dep)):
    return continuidade.ranking_alimentadores(repo, _periodo(repo, inicio, fim), municipio)


@router.get("/alimentadores/{alimentador_id}/serie")
def serie(alimentador_id: str, inicio: str | None = Query(None, pattern=COMP), fim: str | None = Query(None, pattern=COMP),
          repo=Depends(repo_dep)):
    """Série mensal de DEC/FEC. 404 só se o alimentador não existir; período sem dados devolve lista vazia."""
    alimentador_id = alimentador_id.upper()
    if not any(a["id"] == alimentador_id for a in repo.alimentadores()):
        raise HTTPException(404, f"Alimentador {alimentador_id} não encontrado")
    return continuidade.serie_mensal(repo, alimentador_id, _periodo(repo, inicio, fim, desde_o_comeco=True))
