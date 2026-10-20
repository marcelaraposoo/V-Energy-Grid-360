from fastapi import APIRouter, Depends

from app.routers.deps import filtros_dep, periodos_dep, repo_dep
from app.schemas import KpisResponse, SeriePonto, VariacaoResponse
from app.services import dashboard, receita

router = APIRouter(prefix="/api", tags=["dashboard e receita"])


@router.get("/dashboard/kpis", response_model=KpisResponse)
def kpis(periodos=Depends(periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    base, atual = periodos
    return dashboard.kpis(repo, base, atual, f)


@router.get("/dashboard/serie", response_model=list[SeriePonto])
def serie(f=Depends(filtros_dep), repo=Depends(repo_dep)):
    return dashboard.serie(repo, f)


@router.get("/receita/variacao", response_model=VariacaoResponse)
def variacao(agrupar_por: str = "municipio", periodos=Depends(periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    """Drill-down: chame com agrupar_por=municipio, depois filtre municipio=X&agrupar_por=bairro, etc."""
    if agrupar_por not in ("municipio", "bairro", "classe"):
        from fastapi import HTTPException
        raise HTTPException(422, "agrupar_por deve ser municipio, bairro ou classe")
    base, atual = periodos
    return receita.variacao(repo, base, atual, f, agrupar_por)
