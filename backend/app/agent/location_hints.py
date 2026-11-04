import logging
import re
import sqlite3
import unicodedata
from functools import lru_cache

from app.core.config import settings


logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, str], set[str]]:
    """Bairros base normalizados para o nome base e municípios normalizados."""
    uri = f"file:{settings.sqlite_path}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            municipios = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT municipio FROM dim_uc"
                )
            }
            bairros = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT bairro FROM dim_uc"
                )
            }
        finally:
            con.close()
    except sqlite3.Error:
        logger.warning(
            "Não foi possível carregar dicas de localização do banco Gold.",
            exc_info=True,
        )
        return {}, set()

    bases = {}
    for bairro in bairros:
        raiz = re.sub(r"\s+(I|II|III|IV|V|\d+)$", "", bairro).strip()
        bases[_norm(raiz)] = raiz
    return bases, {_norm(municipio) for municipio in municipios}


def neighborhood_hint(question: str) -> str | None:
    bairros, municipios = _load()
    q = _norm(question)
    found = []
    words = set(re.findall(r"[a-z0-9]+", q))
    for key, name in bairros.items():
        if key in municipios or len(key) < 4:
            continue
        key_words = key.split()
        if all(w in words for w in key_words):
            found.append(name)
    if not found:
        return None
    nomes = ", ".join(f"'{name}'" for name in found)
    return (
        f"Dica de interpretação: {nomes} é(são) bairro(s), não município. "
        "Filtre por `bairro LIKE 'Nome%'` e inclua `municipio` e `bairro` "
        "no SELECT e no GROUP BY."
    )
