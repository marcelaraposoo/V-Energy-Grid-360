from fastapi import APIRouter, Depends, Query, Response

from app.routers.deps import repo_dep
from app.schemas import Ordem, OrdemCreate, ResultadoInspecao, SuspeitaFila
from app.services import perdas

router = APIRouter(prefix="/api/perdas", tags=["perdas"])


@router.get("/fila", response_model=list[SuspeitaFila])
def fila(response: Response, q: str | None = Query(None, max_length=100, description="busca por UC ou titular"),
         municipio: str | None = None, classe: str | None = None, prob_minima: float = Query(0, ge=0, le=1),
         pagina: int = Query(1, ge=1), tamanho: int = Query(20, ge=1, le=100), repo=Depends(repo_dep)):
    """Fila priorizada de suspeitas. O total de itens (após os filtros) vai no cabeçalho `X-Total-Count`."""
    itens, total = perdas.fila(repo, municipio, classe, prob_minima, q, pagina, tamanho)
    response.headers["X-Total-Count"] = str(total)
    return itens


@router.post("/ordens", response_model=Ordem, status_code=201)
def criar(dados: OrdemCreate, repo=Depends(repo_dep)):
    return perdas.criar(repo, dados)


@router.get("/ordens", response_model=list[Ordem])
def listar(status: str | None = None, repo=Depends(repo_dep)):
    return repo.listar_ordens(status)


@router.get("/ordens/{ordem_id}", response_model=Ordem)
def obter(ordem_id: int, repo=Depends(repo_dep)):
    return perdas.obter(repo, ordem_id)


@router.post("/ordens/{ordem_id}/iniciar", response_model=Ordem)
def iniciar(ordem_id: int, repo=Depends(repo_dep)):
    return perdas.iniciar(repo, ordem_id)


@router.post("/ordens/{ordem_id}/resultado", response_model=Ordem)
def resultado(ordem_id: int, r: ResultadoInspecao, repo=Depends(repo_dep)):
    return perdas.registrar_resultado(repo, ordem_id, r)


@router.post("/ordens/{ordem_id}/cancelar", response_model=Ordem)
def cancelar(ordem_id: int, repo=Depends(repo_dep)):
    return perdas.cancelar(repo, ordem_id)
