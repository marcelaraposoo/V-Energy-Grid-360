from dataclasses import dataclass
from pathlib import Path

from app.agent.state.audit import AuditStore
from app.agent.state.cache import (
    CacheStore,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    validate_cache_ttl,
    validate_cache_timeout,
)
from app.agent.state.cache_key import has_data_version
from app.agent.state.memory import MemoryStore, DEFAULT_MEMORY_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class AgentStateDependencies:
    """
    Stores e limites usados pela C2 e pela finalização C7.

    Stores opcionais permitem injeção isolada nos testes. A versão Gold inclui
    o identificador explícito da integração; o factory acrescenta a identidade
    do arquivo local. Não há cálculo de hash do conteúdo Gold por GET.
    """

    audit_store: AuditStore | None = None
    memory_store: MemoryStore | None = None
    cache_store: CacheStore | None = None
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    cache_timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS
    data_version: str | None = None
    memory_timeout_seconds: float = DEFAULT_MEMORY_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.memory_store is not None:
            validate_cache_timeout(self.memory_timeout_seconds)
        if self.cache_store is None:
            return

        if not has_data_version(self.data_version):
            raise ValueError(
                "data_version é obrigatória quando cache_store estiver configurado."
            )
        validate_cache_ttl(self.cache_ttl_seconds)
        validate_cache_timeout(self.cache_timeout_seconds)


def get_state_dependencies() -> AgentStateDependencies:
    """Adapters C2/C7, sem conexão antecipada com Redis ou SQLite."""
    from app.core.config import settings
    from app.agent.state.redis_cache import RedisCacheStore
    from app.agent.state.redis_memory import RedisMemoryStore
    from app.agent.state.sqlite_audit import SQLiteAuditStore

    version = settings.gold_data_version
    if version and settings.redis_url:
        try:
            snapshot = Path(settings.sqlite_path).stat()
            version = f"{version}:file:{snapshot.st_size}:{snapshot.st_mtime_ns}"
        except OSError:
            # A indisponibilidade do arquivo é reportada pela execução; ela não
            # autoriza recuperar uma resposta de um snapshot que não está legível.
            version += ":file:unavailable"
    return AgentStateDependencies(
        audit_store=SQLiteAuditStore(settings.portal_db_path),
        memory_store=(
            RedisMemoryStore(
                settings.redis_url, ttl_seconds=settings.memory_ttl_seconds,
                timeout_seconds=settings.memory_timeout_seconds,
            ) if settings.redis_url else None
        ),
        memory_timeout_seconds=settings.memory_timeout_seconds,
        cache_store=(
            RedisCacheStore(settings.redis_url, timeout_seconds=settings.cache_timeout_seconds, max_entries_per_session=settings.cache_max_entries_per_session)
            if settings.redis_url else None
        ),
        data_version=version,
        cache_ttl_seconds=settings.cache_ttl_seconds,
        cache_timeout_seconds=settings.cache_timeout_seconds,
    )
