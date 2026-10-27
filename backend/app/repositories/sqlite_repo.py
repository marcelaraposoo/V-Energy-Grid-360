"""TODO: implementar quando o banco SQLite com as tabelas Gold estiver pronto.
Implementar os mesmos métodos de repositories/base.py::Repository lendo de settings.sqlite_path.
As ordens de inspeção pertencem ao PORTAL (não à Gold) e já têm armazém próprio: nos quatro métodos de ordens,
delegar para `get_ordens_store()` (repositories/__init__.py), que usa `settings.portal_db_path` (data/portal.db)."""


class SqliteRepository:
    def __init__(self, path: str) -> None:
        raise NotImplementedError("Repositório SQLite ainda não implementado — use DATA_SOURCE=mock.")
