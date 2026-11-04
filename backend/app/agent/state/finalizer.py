import asyncio
import logging
from app.core.observability import observe, set_metadata

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
from app.agent.state.memory import (
    MemoryStore, should_store_in_memory, DEFAULT_MEMORY_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)


@observe("C7")
async def finalize(
    *,
    audit_store: AuditStore | None,
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
    memory_timeout_seconds: float = DEFAULT_MEMORY_TIMEOUT_SECONDS,
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

    set_metadata(
        request_id=audit_record.request_id, outcome=audit_record.outcome.value,
        cache_hit=audit_record.cache_hit, row_count=audit_record.row_count,
        truncated=audit_record.truncated, regenerations=audit_record.regenerations,
    )

    try:
        if audit_store is not None:
            async with asyncio.timeout(2.0):
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
            async with asyncio.timeout(memory_timeout_seconds):
                append_turn = True
                if audit_record.cache_hit:
                    entries = await memory_store.get_context(audit_record.session_id)
                    if entries:
                        last = entries[-1]
                        append_turn = (last.question, last.answer, last.outcome) != (
                            memory_entry.question, memory_entry.answer, memory_entry.outcome,
                        )
                if append_turn:
                    await memory_store.append(audit_record.session_id, memory_entry)
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
        # Só a finalização elegível publica o certificado, após C4.2/C4.3/C5/C6.
        from app.agent.state.cache_eligibility import prove_independence, independent_lookup_key
        proof = prove_independence(audit_record.question, audit_record.sql)
        from app.agent.state.sql_cache import sql_cache_plan, canonical_cache_sql, record_cache
        if audit_record.sql is not None and canonical_cache_sql(audit_record.sql) is None:
            record_cache("unsupported_plan", "post_sql")
            return
        plan = sql_cache_plan(audit_record.question, audit_record.sql, audit_record.session_id, cache_data_version)
        approved_setter = getattr(cache_store, "set_approved", None)
        if plan is not None and callable(approved_setter):
            independent = None
            if proof is not None:
                independent = (independent_lookup_key(audit_record.question, audit_record.session_id, cache_data_version), proof)
            try:
                async with asyncio.timeout(cache_timeout_seconds):
                    await approved_setter(cache_key, cache_value, cache_ttl_seconds, plan=plan, independent=independent)
                return
            except Exception as error:
                logger.warning("Falha ao persistir cache por plano. error_type=%s", type(error).__name__)
        setter = getattr(cache_store, "set_independent", None)
        if proof is not None and audit_record.session_id and callable(setter):
            lookup = independent_lookup_key(audit_record.question, audit_record.session_id, cache_data_version)
            try:
                async with asyncio.timeout(cache_timeout_seconds):
                    await setter(cache_key, cache_value, cache_ttl_seconds, lookup_key=lookup, eligibility=proof)
                return
            except Exception as error:
                logger.warning("Falha ao persistir cache independente. error_type=%s", type(error).__name__)
        await write_cache(
            cache_store,
            cache_key,
            cache_value,
            ttl_seconds=cache_ttl_seconds,
            timeout_seconds=cache_timeout_seconds,
        )
