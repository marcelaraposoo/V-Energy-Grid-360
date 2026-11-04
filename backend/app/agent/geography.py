"""Desambiguação por catálogo local; não consulta nem altera memória/cache."""
import re
import sqlite3
from time import monotonic
from app.agent.conversation import normalize
from app.core.config import settings


def geographic_clarification(question, database_path=None):
    # Priorize o nível explícito: "no município" também define geografia.
    explicit = re.search(r"\b(?:no|em|do) (?:o )?munic[ií]pio (?:de |do |da )?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]*?)(?=\s+(?:entre|durante|nos|no|na)|[?,]|$)", question, re.I)
    match = explicit or re.search(r"\bem\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]*?)(?=\s+(?:entre|durante|nos|no|na|de \d)|[?]|$)", question, re.I)
    if not match:
        return None
    raw_place = match[1].strip()
    place = re.sub(r"^(?:o |a )?municipio (?:de |do |da )?", "", normalize(match[1].strip()))
    try:
        from pathlib import Path
        uri = Path(database_path or settings.sqlite_path).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri,uri=True,timeout=.2) as connection:
            deadline = monotonic() + .3
            connection.set_progress_handler(lambda: monotonic() > deadline, 10000)
            rows = connection.execute("SELECT DISTINCT municipio,bairro FROM dim_uc").fetchall()
        municipalities = {normalize(str(m)) for m,b in rows if m}
        candidates = {(m,b) for m,b in rows if b and (normalize(b)==place or normalize(b).startswith(place+" "))}
        if len(candidates) == 1:
            municipality, neighborhood = next(iter(candidates))
            if normalize(neighborhood) == place and normalize(municipality) in normalize(question):
                return None
        if place not in municipalities and not candidates and (raw_place[0].isupper() or explicit is not None or "municipio" in normalize(raw_place)):
            return "Não encontrei essa localidade no cadastro disponível da Gold. Confirme o município ou bairro; ausência de cobertura não comprova zero ocorrências."
        if candidates and (place not in municipalities or len({m for m,b in candidates})>1):
            return "Você se refere a um município ou a um bairro? Para bairros, informe também o município e o nome completo da localidade."
    except (OSError,sqlite3.Error,ValueError):
        return None
    return None
