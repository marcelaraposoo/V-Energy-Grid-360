from __future__ import annotations

from fastapi import Depends, HTTPException, Query

from app.repositories import get_repo
from app.schemas import Filtros, Periodo
from app.services.dashboard import periodos_padrao

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
    return base, atual
