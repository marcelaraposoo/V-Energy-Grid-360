class NaoEncontrado(Exception):
    """Recurso inexistente -> HTTP 404."""


class ConflitoDeEstado(Exception):
    """Operação inválida para o estado atual (ex.: cancelar ordem já concluída) -> HTTP 409."""


class NaoDisponivelNaGold(Exception):
    """O dado depende de uma tabela que a Gold ainda não entregou (SQLite) -> HTTP 501."""
