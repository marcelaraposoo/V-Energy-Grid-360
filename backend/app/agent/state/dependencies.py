from dataclasses import dataclass

from app.agent.state.audit import AuditStore
from app.agent.state.cache import (
    CacheStore,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    validate_cache_ttl,
    validate_cache_timeout,
)
from app.agent.state.cache_key import has_data_version
from app.agent.state.memory import MemoryStore


@dataclass(frozen=True, slots=True)
class AgentStateDependencies:
    """
    Contratos de estado compartilhados pela C2 e pela futura finalização.

    A auditoria é uma interface opcional para a futura C7. A versão Gold é um
    identificador explícito fornecido pela integração, nunca mtime/hash por GET.
    """

    audit_store: AuditStore | None = None
    memory_store: MemoryStore | None = None
    cache_store: CacheStore | None = None
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    cache_timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS
    data_version: str | None = None

    def __post_init__(self) -> None:
        if self.cache_store is None:
            return

        if not has_data_version(self.data_version):
            raise ValueError(
                "data_version é obrigatória quando cache_store estiver configurado."
            )
        validate_cache_ttl(self.cache_ttl_seconds)
        validate_cache_timeout(self.cache_timeout_seconds)


def get_state_dependencies() -> AgentStateDependencies:
    """Configuração operacional da C2, sem conexão antecipada com Redis."""
    from app.core.config import settings
    from app.agent.state.redis_cache import RedisCacheStore

    return AgentStateDependencies(
        cache_store=(
            RedisCacheStore(settings.redis_url, timeout_seconds=settings.cache_timeout_seconds)
            if settings.redis_url else None
        ),
        data_version=settings.gold_data_version,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        cache_timeout_seconds=settings.cache_timeout_seconds,
    )
