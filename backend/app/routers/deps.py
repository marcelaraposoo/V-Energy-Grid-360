from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from app.repositories import get_repo
from app.schemas import Filtros, Periodo
from app.services.dashboard import periodos_padrao
from app.services.dashboard_periodos import sugerir_referencia, validar_periodos

COMP = r"^\d{4}-(0[1-9]|1[0-2])$"


def repo_dep():
    return get_repo()


def filtros_dep(municipio: str | None = None, bairro: str | None = None, classe: str | None = None,
                repo=Depends(repo_dep)) -> Filtros:
    """Valida os filtros contra os catálogos (valor desconhecido = 422, e não uma tela cheia de zeros)."""
    mun_bairros = repo.municipios_bairros()
    if municipio is not None and municipio not in mun_bairros:
        raise HTTPException(422, f"Município desconhecido: {municipio}")
    if classe is not None and classe not in repo.classes():
        raise HTTPException(422, f"Classe desconhecida: {classe}")
    if bairro is not None:
        candidatos = mun_bairros[municipio] if municipio else [b for bs in mun_bairros.values() for b in bs]
        if bairro not in candidatos:
            onde = f" em {municipio}" if municipio else ""
            raise HTTPException(422, f"Bairro desconhecido{onde}: {bairro}")
    return Filtros(municipio=municipio, bairro=bairro, classe=classe)


def municipio_dep(municipio: str | None = None, repo=Depends(repo_dep)) -> str | None:
    """Só município: para os blocos do Dashboard que não descem a bairro nem a classe."""
    if municipio is not None and municipio not in repo.municipios_bairros():
        raise HTTPException(422, f"Município desconhecido: {municipio}")
    return municipio


def periodos_dep(
    base_inicio: str | None = Query(None, pattern=COMP),
    base_fim: str | None = Query(None, pattern=COMP),
    atual_inicio: str | None = Query(None, pattern=COMP),
    atual_fim: str | None = Query(None, pattern=COMP),
    repo=Depends(repo_dep),
) -> tuple[Periodo, Periodo]:
    b, a = periodos_padrao(repo)
    base = Periodo(inicio=base_inicio or b.inicio, fim=base_fim or b.fim)
    atual = Periodo(inicio=atual_inicio or a.inicio, fim=atual_fim or a.fim)
    for p in (base, atual):
        if p.inicio > p.fim:
            raise HTTPException(422, f"Período inválido: início {p.inicio} é maior que o fim {p.fim}")
    # Preço × volume só é comparável entre períodos de mesma duração, sem sobreposição e dentro da base.
    try:
        validar_periodos(atual, base, sorted(set(repo.competencias())))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return base, atual


def dashboard_periodos_dep(
    comparar: bool = True,
    base_inicio: str | None = Query(None, pattern=COMP),
    base_fim: str | None = Query(None, pattern=COMP),
    atual_inicio: str | None = Query(None, pattern=COMP),
    atual_fim: str | None = Query(None, pattern=COMP),
    repo=Depends(repo_dep),
) -> tuple[Periodo | None, Periodo]:
    """Comparação opcional, mantendo base_*/atual_* e os padrões do case."""
    competencias = sorted(set(repo.competencias()))
    if not competencias:
        raise HTTPException(422, "Não existem competências disponíveis para selecionar um período.")
    if (atual_inicio is None) != (atual_fim is None):
        raise HTTPException(422, "Informe início e fim do período analisado.")
    if (base_inicio is None) != (base_fim is None):
        raise HTTPException(422, "Informe início e fim do período de referência.")
    atual = Periodo(inicio=atual_inicio or competencias[-min(12, len(competencias))], fim=atual_fim or competencias[-1])
    base = None
    try:
        if comparar:
            if base_inicio is not None:
                base = Periodo(inicio=base_inicio, fim=base_fim)
            elif atual_inicio is None and len(competencias) >= 24:
                # Sem parâmetros temporais: mantém a referência inicial do backend.
                base = Periodo(inicio=competencias[0], fim=competencias[11])
            else:
                base = sugerir_referencia(atual, competencias)
            if base is None:
                raise ValueError("Não existe referência automática válida. Informe base_inicio/base_fim para personalizar ou continue com comparar=false.")
        elif base_inicio is not None:
            raise ValueError("Não envie parâmetros base_* quando comparar=false.")
        validar_periodos(atual, base, competencias)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return base, atual
