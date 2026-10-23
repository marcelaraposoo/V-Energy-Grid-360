"""TODO: implementar quando o banco SQLite com as tabelas Gold estiver pronto.
Implementar os mesmos métodos de repositories/base.py::Repository lendo de settings.sqlite_path.
A tabela de ordens de inspeção pertence ao PORTAL (não à Gold): criar no startup se não existir."""


class SqliteRepository:
    def __init__(self, path: str) -> None:
        raise NotImplementedError("Repositório SQLite ainda não implementado — use DATA_SOURCE=mock.")
