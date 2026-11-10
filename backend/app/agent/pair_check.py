import sqlite3

from sqlglot import exp, parse_one

from app.agent.sql_executor import build_read_only_uri
from app.core.config import settings


def extract_municipality(sql: str) -> str | None:
    """Município só se aparecer como igualdade simples."""
    try:
        where = parse_one(sql, read="sqlite").args.get("where")
    except Exception:
        return None
    if where is None:
        return None
    for eq in where.find_all(exp.EQ):
        col, val = eq.this, eq.expression
        if (
            isinstance(col, exp.Column)
            and col.name.lower() == "municipio"
            and isinstance(val, exp.Literal)
            and val.is_string
        ):
            return val.this
    return None


def municipality_exists(municipio: str, database_path: str | None = None):
    """True/False, ou None se o catálogo não pôde ser lido."""
    path = database_path or settings.sqlite_path
    try:
        con = sqlite3.connect(build_read_only_uri(path), uri=True)
        try:
            return con.execute(
                "SELECT 1 FROM dim_uc WHERE municipio = ? LIMIT 1", (municipio,)
            ).fetchone() is not None
        finally:
            con.close()
    except Exception:
        return None


MUNICIPALITY_MESSAGE = (
    "Não encontrei esse local como município no cadastro. "
    "Confirme se é um município ou um bairro e informe o município correspondente."
)


def extract_pair(sql: str) -> tuple[str, str] | None:
    """(municipio, bairro) só se ambos aparecerem como igualdade simples."""
    try:
        where = parse_one(sql, read="sqlite").args.get("where")
    except Exception:
        return None
    if where is None:
        return None
    found: dict[str, str] = {}
    for eq in where.find_all(exp.EQ):
        col, val = eq.this, eq.expression
        if (
            isinstance(col, exp.Column)
            and isinstance(val, exp.Literal)
            and val.is_string
            and col.name.lower() in {"municipio", "bairro"}
        ):
            found[col.name.lower()] = val.this
    if "municipio" in found and "bairro" in found:
        return found["municipio"], found["bairro"]
    return None


def is_empty_or_zero(columns, rows) -> bool:
    if not rows:
        return True
    if all(value is None for row in rows for value in row):
        return True
    return len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] in (None, 0, 0.0)


def lookup_pair(municipio: str, bairro: str, database_path: str | None = None):
    """
    Devolve ('exists', None) | ('other', [municípios do catálogo]) |
    ('missing', None) | None se o catálogo não pôde ser lido.
    """
    path = database_path or settings.sqlite_path
    try:
        con = sqlite3.connect(build_read_only_uri(path), uri=True)
        try:
            if con.execute(
                "SELECT 1 FROM dim_uc WHERE municipio = ? AND bairro = ? LIMIT 1",
                (municipio, bairro),
            ).fetchone():
                return "exists", None
            others = [
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT municipio FROM dim_uc WHERE bairro = ? "
                    "ORDER BY municipio LIMIT 5",
                    (bairro,),
                )
            ]
        finally:
            con.close()
    except Exception:
        return None
    return ("other", others) if others else ("missing", None)


def clarification_message(status: str, bairro_ok: str | None, others) -> str:
    """Só usa nomes que vieram do catálogo (others); nunca literais do usuário."""
    if status == "other" and others:
        lista = ", ".join(others)
        return (
            "Não encontrei esse bairro no município citado. "
            f"Esse bairro existe em: {lista}. Qual deles você quer consultar?"
        )
    return (
        "Não encontrei esse bairro no município citado. "
        "Confira o nome do bairro e do município e tente novamente."
    )
