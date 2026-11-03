"""Regras temporais exclusivas do Dashboard; não altera o contrato da Gold."""
import re

from app.schemas import Periodo


def indice_mes(mes: str) -> int:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
        raise ValueError("Competência inválida; use YYYY-MM.")
    return int(mes[:4]) * 12 + int(mes[5:]) - 1


def quantidade_meses(periodo: Periodo) -> int:
    return indice_mes(periodo.fim) - indice_mes(periodo.inicio) + 1


def deslocar_mes(mes: str, quantidade: int) -> str:
    ano, indice = divmod(indice_mes(mes) + quantidade, 12)
    return f"{ano:04d}-{indice + 1:02d}"


def validar_periodos(atual: Periodo, base: Periodo | None, competencias: list[str]) -> None:
    comparar = base is not None
    disponiveis = set(competencias)
    for periodo in (atual, base):
        if periodo is None:
            continue
        duracao = quantidade_meses(periodo)
        limite = 12 if comparar else 24
        if not 1 <= duracao <= limite:
            raise ValueError(f"Selecione de 1 a {limite} meses por período.")
        if any(deslocar_mes(periodo.inicio, i) not in disponiveis for i in range(duracao)):
            raise ValueError("O período deve estar dentro das competências disponíveis na base.")
    if base is not None:
        if quantidade_meses(atual) != quantidade_meses(base):
            raise ValueError("Os períodos devem ter a mesma quantidade de competências.")
        if atual.inicio <= base.fim and base.inicio <= atual.fim:
            raise ValueError("Os períodos não podem se sobrepor.")


def sugerir_referencia(atual: Periodo, competencias: list[str]) -> Periodo | None:
    duracao = quantidade_meses(atual)
    candidatas = [
        Periodo(inicio=deslocar_mes(atual.inicio, -12), fim=deslocar_mes(atual.fim, -12)),
        Periodo(inicio=deslocar_mes(atual.inicio, -duracao), fim=deslocar_mes(atual.inicio, -1)),
    ]
    for base in candidatas:
        try:
            validar_periodos(atual, base, competencias)
        except ValueError:
            continue
        return base
    return None
