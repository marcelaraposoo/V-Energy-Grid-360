from typing import Literal

from fastapi import APIRouter, Depends, Request

from app.routers.deps import dashboard_periodos_dep, filtros_dep, municipio_dep, periodos_dep, repo_dep
from app.schemas import CadastroGdResponse, ConsumoClassesResponse, ConsumoLocaisResponse, KpisResponse, OperacaoResponse, SeriePonto, VariacaoResponse
from app.services import dashboard, dashboard_complementares, receita

router = APIRouter(prefix="/api", tags=["dashboard e receita"])


@router.get("/dashboard/kpis", response_model=KpisResponse)
def kpis(indicador: Literal["inadimplencia", "executivo"] | None = None, periodos=Depends(dashboard_periodos_dep), f=Depends(filtros_dep), repo=Depends(repo_dep)):
    base, atual = periodos
    return dashboard.kpis(repo, base, atual, f, indicador=indicador)


@router.get("/dashboard/cadastro-gd", response_model=CadastroGdResponse)
def cadastro_gd(periodos=Depends(dashboard_periodos_dep), municipio=Depends(municipio_dep), repo=Depends(repo_dep)):
    base, atual = periodos
    return dashboard_complementares.cadastro_gd(repo, base, atual, municipio)


@router.get("/dashboard/consumo-classes", response_model=ConsumoClassesResponse)
def consumo_classes(periodos=Depends(dashboard_periodos_dep), municipio=Depends(municipio_dep), repo=Depends(repo_dep)):
    base, atual = periodos
    return dashboard_complementares.consumo_classes(repo, base, atual, municipio)


@router.get("/dashboard/consumo-locais", response_model=ConsumoLocaisResponse)
def consumo_locais(periodos=Depends(dashboard_periodos_dep), municipio=Depends(municipio_dep), repo=Depends(repo_dep)):
    """Energia por município (distribuidora) ou por bairro (com município escolhido)."""
    base, atual = periodos
    return dashboard_complementares.consumo_locais(repo, base, atual, municipio)


@router.get("/dashboard/operacao", response_model=OperacaoResponse)
def operacao(periodos=Depends(dashboard_periodos_dep), municipio=Depends(municipio_dep), repo=Depends(repo_dep)):
    """Atendimentos e satisfação (B1) e DEC/FEC (A8) da distribuidora ou de um município."""
    base, atual = periodos
    return dashboard_complementares.operacao(repo, base, atual, municipio)


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
