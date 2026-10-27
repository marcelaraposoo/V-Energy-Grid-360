from functools import lru_cache

from app.core.config import settings
from app.repositories.base import OrdensStore, Repository


@lru_cache(maxsize=1)
def get_ordens_store() -> OrdensStore:
    """Armazém das ordens de inspeção (SQLite do portal). Compartilhado por qualquer Repository."""
    from app.repositories.ordens_store import SqliteOrdensStore
    return SqliteOrdensStore(settings.portal_db_path)


@lru_cache(maxsize=1)
def get_repo() -> Repository:
    if settings.data_source == "sqlite":
        from app.repositories.sqlite_repo import SqliteRepository
        return SqliteRepository(settings.sqlite_path)
    from app.repositories.mock_repo import MockRepository
    return MockRepository(ordens=get_ordens_store())
