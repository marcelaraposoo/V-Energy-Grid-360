from dataclasses import dataclass

from app.agent.state.audit import AuditStore
from app.agent.state.cache import CacheStore
from app.agent.state.memory import MemoryStore


@dataclass(frozen=True, slots=True)
class AgentStateDependencies:
    """
    Dependências externas utilizadas pela Camada 7.

    O pipeline conhece apenas os contratos (Protocols).
    As implementações reais de banco e Redis são injetadas depois.
    """

    audit_store: AuditStore
    memory_store: MemoryStore | None = None
    cache_store: CacheStore | None = None
    cache_ttl_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.cache_store is None:
            return

        if (
            self.cache_ttl_seconds is None
            or self.cache_ttl_seconds <= 0
        ):
            raise ValueError(
                "cache_ttl_seconds deve ser maior que zero "
                "quando cache_store estiver configurado."
            )