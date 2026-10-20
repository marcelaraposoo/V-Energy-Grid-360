from __future__ import annotations

from fastapi import Depends, Query

from app.repositories import get_repo
from app.schemas import Filtros, Periodo
from app.services.dashboard import periodos_padrao

COMP = r"^\d{4}-(0[1-9]|1[0-2])$"


def repo_dep():
    return get_repo()


def filtros_dep(municipio: str | None = None, bairro: str | None = None, classe: str | None = None) -> Filtros:
    return Filtros(municipio=municipio, bairro=bairro, classe=classe)


def periodos_dep(
    base_inicio: str | None = Query(None, pattern=COMP),
    base_fim: str | None = Query(None, pattern=COMP),
    atual_inicio: str | None = Query(None, pattern=COMP),
    atual_fim: str | None = Query(None, pattern=COMP),
    repo=Depends(repo_dep),
) -> tuple[Periodo, Periodo]:
    b, a = periodos_padrao(repo)
    return (
        Periodo(inicio=base_inicio or b.inicio, fim=base_fim or b.fim),
        Periodo(inicio=atual_inicio or a.inicio, fim=atual_fim or a.fim),
    )
