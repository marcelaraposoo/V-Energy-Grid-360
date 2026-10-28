from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import COMP, repo_dep
from app.schemas import PERIODO_HISTORICO_PADRAO, PeriodoHistorico, Visao360
from app.services import unidades

router = APIRouter(prefix="/api/unidades", tags=["unidades consumidoras"])


@router.get("")
def buscar(q: str | None = None, municipio: str | None = None, classe: str | None = None,
           limite: int = Query(20, ge=1, le=100), repo=Depends(repo_dep)):
    return repo.buscar_ucs(q, municipio, classe, limite)


@router.get("/{uc_id}/visao-360", response_model=Visao360)
def visao_360(
    uc_id: str,
    competencia_atual: str | None = Query(None, pattern=COMP),
    competencia_referencia: str | None = Query(None, pattern=COMP),
    periodo_interrupcoes: PeriodoHistorico = Query(PERIODO_HISTORICO_PADRAO),
    periodo_atendimentos: PeriodoHistorico = Query(PERIODO_HISTORICO_PADRAO),
    repo=Depends(repo_dep),
):
    try:
        return unidades.visao_360(
            repo, uc_id, competencia_atual, competencia_referencia,
            periodo_interrupcoes, periodo_atendimentos,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
