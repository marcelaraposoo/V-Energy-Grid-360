from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.routers.deps import repo_dep
from app.schemas import Ordem, OrdemCreate, RejeicaoImportacao, ResultadoInspecao, ResumoImportacao, SuspeitaFila
from app.services import exportacao, importacao, perdas

router = APIRouter(prefix="/api/perdas", tags=["perdas"])


@router.get("/fila", response_model=list[SuspeitaFila])
def fila(response: Response, q: str | None = Query(None, max_length=100, description="busca por UC ou titular"),
         municipio: str | None = None, classe: str | None = None, prob_minima: float = Query(0, ge=0, le=1),
         pagina: int = Query(1, ge=1), tamanho: int = Query(20, ge=1, le=100), repo=Depends(repo_dep)):
    """Fila priorizada de suspeitas. O total de itens (após os filtros) vai no cabeçalho `X-Total-Count`."""
    itens, total = perdas.fila(repo, municipio, classe, prob_minima, q, pagina, tamanho)
    response.headers["X-Total-Count"] = str(total)
    return itens


@router.get("/fila/exportar", responses={200: {"description": "Arquivo CSV (UTF-8, separador `;`)", "content": {"text/csv": {}}}})
def exportar_fila(q: str | None = Query(None, max_length=100, description="busca por UC ou titular"),
                  municipio: str | None = None, classe: str | None = None, prob_minima: float = Query(0, ge=0, le=1),
                  limite: int = Query(500, ge=1, le=5000, description="quantas suspeitas exportar, da mais prioritária para baixo"),
                  repo=Depends(repo_dep)):
    """Exporta a fila (com os mesmos filtros de `/fila`, sem paginação) em CSV para enviar à equipe de campo.
    `X-Total-Count` traz o total da fila filtrada, mesmo quando `limite` corta o arquivo."""
    itens, total = perdas.fila(repo, municipio, classe, prob_minima, q, 1, limite)
    nome = f"fila-inspecao-{date.today().isoformat()}.csv"
    return Response(content=exportacao.fila_para_csv(itens).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"', "X-Total-Count": str(total)})


@router.post("/ordens", response_model=Ordem, status_code=201)
def criar(dados: OrdemCreate, repo=Depends(repo_dep)):
    return perdas.criar(repo, dados)


@router.get("/ordens", response_model=list[Ordem])
def listar(status: str | None = None, repo=Depends(repo_dep)):
    return repo.listar_ordens(status)


@router.get("/ordens/resultados/modelo", responses={200: {"description": "Arquivo CSV (UTF-8, separador `;`)", "content": {"text/csv": {}}}})
def modelo_resultados(repo=Depends(repo_dep)):
    """Modelo de planilha para a equipe de campo: uma linha por ordem em aberto, colunas de resultado vazias."""
    abertas = sorted((o for o in repo.listar_ordens() if o["status"] in perdas.ATIVAS), key=lambda o: o["id"])
    nome = f"resultados-inspecao-{date.today().isoformat()}.csv"
    return Response(content=importacao.modelo_para_csv(abertas).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


def _importar(conteudo: bytes, repo) -> ResumoImportacao:
    try:
        linhas = importacao.ler_planilha(conteudo)
    except importacao.PlanilhaInvalida as erro:
        raise HTTPException(422, str(erro)) from erro
    aceitas, ignoradas, rejeitadas = 0, 0, []
    for l in linhas:
        if l.pendente:
            ignoradas += 1
        elif l.erro:
            rejeitadas.append(RejeicaoImportacao(linha=l.linha, ordem_id=l.ordem_id, erro=l.erro))
        else:
            try:
                perdas.registrar_resultado(repo, l.ordem_id, ResultadoInspecao(
                    tipo=l.tipo, energia_recuperada_kwh=l.energia_recuperada_kwh, observacoes=l.observacoes))
                aceitas += 1
            except (NaoEncontrado, ConflitoDeEstado) as erro:
                rejeitadas.append(RejeicaoImportacao(linha=l.linha, ordem_id=l.ordem_id, erro=str(erro)))
    return ResumoImportacao(total=aceitas + len(rejeitadas), aceitas=aceitas, ignoradas=ignoradas, rejeitadas=rejeitadas)


@router.post("/ordens/resultados/importar", response_model=ResumoImportacao)
async def importar_resultados(request: Request, repo=Depends(repo_dep)):
    """Recebe o CSV preenchido (corpo da requisição, `Content-Type: text/csv`) e registra cada resultado válido.
    Linhas com erro não são registradas e voltam listadas com o motivo; as demais seguem normalmente."""
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > importacao.TAMANHO_MAXIMO:
        raise HTTPException(413, "O arquivo é grande demais (limite de 1 MB).")
    return await run_in_threadpool(_importar, await request.body(), repo)


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
