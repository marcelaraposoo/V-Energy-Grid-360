import logging

from app.agent.schemas import (
    AuditRecord,
    MemoryEntry,
    PostProcessingResult,
)
from app.agent.state.audit import AuditStore
from app.agent.state.cache import CacheStore, should_store_in_cache
from app.agent.state.memory import MemoryStore, should_store_in_memory


logger = logging.getLogger(__name__)


async def finalize(
    *,
    audit_store: AuditStore,
    audit_record: AuditRecord,
    memory_store: MemoryStore | None = None,
    memory_entry: MemoryEntry | None = None,
    cache_store: CacheStore | None = None,
    cache_key: str | None = None,
    cache_value: PostProcessingResult | None = None,
    cache_ttl_seconds: int | None = None,
) -> None:
    """
    Finaliza uma execução do agente.

    Regras:
    - auditoria é sempre tentada;
    - memória só é atualizada para outcomes elegíveis e com sessão;
    - cache só recebe respostas elegíveis;
    - cache hit não reescreve o mesmo valor;
    - falhas de persistência não impedem a resposta ao usuário.
    """

    try:
        await audit_store.save(audit_record)
    except Exception as error:
        logger.warning(
            "Falha ao persistir auditoria. error_type=%s",
            type(error).__name__,
        )

    if (
        memory_store is not None
        and memory_entry is not None
        and audit_record.session_id is not None
        and should_store_in_memory(audit_record.outcome)
    ):
        try:
            await memory_store.append(
                audit_record.session_id,
                memory_entry,
            )
        except Exception as error:
            logger.warning(
                "Falha ao persistir memória. error_type=%s",
                type(error).__name__,
            )

    if (
        cache_store is not None
        and cache_key is not None
        and cache_value is not None
        and cache_ttl_seconds is not None
        and cache_ttl_seconds > 0
        and not audit_record.cache_hit
        and should_store_in_cache(audit_record.outcome)
    ):
        try:
            await cache_store.set(
                cache_key,
                cache_value,
                cache_ttl_seconds,
            )
        except Exception as error:
            logger.warning(
                "Falha ao persistir cache. error_type=%s",
                type(error).__name__,
            )