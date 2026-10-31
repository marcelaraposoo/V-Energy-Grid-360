from functools import lru_cache
from pathlib import Path


CONTEXT_PATH = Path(__file__).resolve().parent / "gold_schema_context.md"


@lru_cache(maxsize=1)
def load_database_context() -> str:
    content = CONTEXT_PATH.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(f"Contexto do banco vazio: {CONTEXT_PATH}")

    return content