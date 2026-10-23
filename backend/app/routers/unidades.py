from fastapi import APIRouter, Depends, Query

from app.routers.deps import repo_dep
from app.schemas import Visao360
from app.services import unidades

router = APIRouter(prefix="/api/unidades", tags=["unidades consumidoras"])


@router.get("")
def buscar(q: str | None = None, municipio: str | None = None, classe: str | None = None,
           limite: int = Query(20, ge=1, le=100), repo=Depends(repo_dep)):
    return repo.buscar_ucs(q, municipio, classe, limite)


@router.get("/{uc_id}/visao-360", response_model=Visao360)
def visao_360(uc_id: str, repo=Depends(repo_dep)):
    return unidades.visao_360(repo, uc_id)
