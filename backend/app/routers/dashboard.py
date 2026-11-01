from typing import Literal

from fastapi import APIRouter, Depends, Request

from app.routers.deps import dashboard_periodos_dep, filtros_dep, periodos_dep, repo_dep
from app.schemas import KpisResponse, SeriePonto, VariacaoResponse
from app.services import dashboard, receita

router = APIRouter(prefix="/api", tags=["dashboard e receita"])


@router.get("/dashboard/kpis", response_model=KpisResponse)
def kpis(indicador: Literal["inadimplencia"] | None = None, periodos=Depends(dashboard_periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    base, atual = periodos
    return dashboard.kpis(repo, base, atual, f, indicador=indicador)


@router.get("/dashboard/serie", response_model=list[SeriePonto])
def serie(request: Request, periodos=Depends(dashboard_periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    temporais = {"comparar", "base_inicio", "base_fim", "atual_inicio", "atual_fim"}
    # Clientes anteriores continuam recebendo toda a série quando só enviam filtros regionais.
    return dashboard.serie(repo, f, periodos if temporais.intersection(request.query_params) else None)


@router.get("/receita/variacao", response_model=VariacaoResponse)
def variacao(agrupar_por: Literal["municipio", "bairro", "classe"] = "municipio", periodos=Depends(periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    """Drill-down: chame com agrupar_por=municipio, depois filtre municipio=X&agrupar_por=bairro, etc."""
    base, atual = periodos
    return receita.variacao(repo, base, atual, f, agrupar_por)
