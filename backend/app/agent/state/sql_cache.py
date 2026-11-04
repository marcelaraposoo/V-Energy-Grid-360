"""Lookup geral após C4.2: mesma pergunta e mesmo SQL determinístico no snapshot."""
from dataclasses import dataclass
import asyncio
import hashlib
from sqlglot import parse, exp
from app.agent.schemas import PostProcessingResult
from app.agent.state.cache_key import build_cache_key
from app.core.observability import observe, set_metadata

CONTRACT = "validated-sql-plan-v2"
# Funções não reconhecidas não são consideradas determinísticas para cache.
_DETERMINISTIC = {"sum", "avg", "min", "max", "count", "abs", "round", "coalesce", "nullif", "cast", "trycast", "case", "if", "lower", "upper", "length", "trim", "substring", "replace", "concat", "and", "or"}


def record_cache(reason, phase, hit=False):
    try:
        set_metadata(cache_reason=reason, cache_phase=phase, cache_hit=hit)
    except Exception:
        pass


@dataclass(frozen=True)
class SQLCachePlan:
    digest: str
    lookup: str

    def metadata(self):
        return {"lookup": self.lookup, "digest": self.digest, "contract": CONTRACT}


def _normalize_output_aliases(tree):
    """Resolve somente aliases de saída locais, sem inferir equivalência de métricas.

    O payload já aprovado é autocontido; nomes das colunas não fazem parte do
    contrato HTTP do HIT. Expressões e a ordenação efetiva precisam ser iguais.
    Bindings ambíguos ou usados fora do ORDER BY conservam a AST original.
    """
    aliases = {item.alias.lower(): item.this for item in tree.expressions if isinstance(item, exp.Alias)}
    aliased_count = sum(isinstance(item, exp.Alias) for item in tree.expressions)
    if not aliases or len(aliases) != aliased_count:
        return tree
    other = tree.copy()
    other.set("order", None)
    # Colunas dentro das projeções são bindings de entrada, inclusive
    # SUM(dec_horas) AS dec_horas; remover o rótulo não muda a expressão.
    other.set("expressions", [])
    if any(column.name.lower() in aliases for column in other.find_all(exp.Column)):
        return tree
    order = tree.args.get("order")
    if order is not None:
        # Subqueries podem ter outro binding; não reinterpretá-las.
        if any(True for _ in order.find_all(exp.Select)):
            return tree
        order = order.copy()
        for column in list(order.find_all(exp.Column)):
            if not column.table and column.name.lower() in aliases:
                column.replace(aliases[column.name.lower()].copy())
        tree.set("order", order)
    tree.set("expressions", [item.unalias().copy() for item in tree.expressions])
    return tree


def canonical_cache_sql(sql):
    try:
        statements = parse(sql, read="sqlite")
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            return None
        tree = statements[0]
        for node in tree.walk():
            if node.comments or isinstance(node, (exp.Placeholder, exp.Parameter)):
                return None
            if isinstance(node, exp.Func) and node.key not in _DETERMINISTIC:
                return None
            if isinstance(node, exp.Literal) and node.is_string and node.this.lower() in {"now", "today", "localtime", "utc"}:
                return None
        if any(select.args.get("limit") and not select.args.get("order") for select in tree.find_all(exp.Select)):
            return None
        return _normalize_output_aliases(tree).sql(dialect="sqlite", normalize=True)
    except Exception:
        return None


def sql_cache_plan(question, sql, session_id, data_version):
    if not isinstance(session_id, str) or not session_id.strip() or not data_version or not sql:
        return None
    canonical = canonical_cache_sql(sql)
    if canonical is None:
        return None
    try:
        digest = hashlib.sha256((CONTRACT + "\n" + canonical).encode()).hexdigest()
        lookup = build_cache_key(normalized_question=question, session_id=session_id,
                                 data_version=data_version, memory_context="sql-plan:" + digest) + ":plan"
        return SQLCachePlan(digest, lookup)
    except Exception:
        return None


@dataclass(frozen=True)
class PlanLookup:
    response: PostProcessingResult | None
    reason: str

    @property
    def cache_hit(self):
        return self.response is not None


@observe("C2")
async def lookup_sql_cache(store, *, question, sql, session_id, data_version, timeout_seconds):
    plan = sql_cache_plan(question, sql, session_id, data_version)
    if plan is None:
        result = PlanLookup(None, "unsupported_plan")
    else:
        try:
            async with asyncio.timeout(timeout_seconds):
                result = await store.get_plan(plan.lookup, digest=plan.digest)
            if not isinstance(result, PlanLookup):
                result = PlanLookup(None, "payload_invalid")
            elif result.response is not None:
                response = PostProcessingResult.model_validate(result.response.model_dump(), strict=True)
                result = PlanLookup(response, "hit")
        except Exception:
            result = PlanLookup(None, "redis_error")
    record_cache(result.reason, "post_sql", result.cache_hit)
    return result
