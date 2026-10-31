import logging

from app.agent.schemas import (
    AuditRecord,
    MemoryEntry,
    PostProcessingResult,
)
from app.agent.state.audit import AuditStore
from app.agent.state.cache import (
    CacheStore,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    should_store_in_cache,
    write_cache,
)
from app.agent.state.cache_key import has_data_version
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
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    cache_timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
    cache_data_version: str | None = None,
    cache_response_complete: bool = False,
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
        and has_data_version(cache_data_version)
        and not audit_record.cache_hit
        and should_store_in_cache(
            audit_record.outcome,
            truncated=audit_record.truncated,
            response_complete=cache_response_complete,
        )
    ):
        await write_cache(
            cache_store,
            cache_key,
            cache_value,
            ttl_seconds=cache_ttl_seconds,
            timeout_seconds=cache_timeout_seconds,
        )
