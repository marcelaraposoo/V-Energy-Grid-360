class NaoEncontrado(Exception):
    """Recurso inexistente -> HTTP 404."""


class ConflitoDeEstado(Exception):
    """Operação inválida para o estado atual (ex.: cancelar ordem já concluída) -> HTTP 409."""
