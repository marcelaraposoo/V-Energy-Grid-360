from fastapi import APIRouter, Depends

from app.routers.deps import repo_dep

router = APIRouter(prefix="/api", tags=["catálogos"])


@router.get("/filtros")
def filtros(repo=Depends(repo_dep)):
    """Opções para os filtros do frontend (selects de município/bairro/classe/alimentador/competência)."""
    return {
        "municipios": [{"nome": m, "bairros": b} for m, b in repo.municipios_bairros().items()],
        "classes": [{"codigo": k, "descricao": v} for k, v in repo.classes().items()],
        "alimentadores": repo.alimentadores(),
        "competencias": repo.competencias(),
    }
