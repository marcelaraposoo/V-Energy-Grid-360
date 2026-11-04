"""Prova limitada: contrato completo da pergunta + equivalência estrutural do SQL.

Não classifica texto livre por palavras-chave. Toda a frase deve pertencer à
linguagem suportada; desconhecidos, referências e filtros extras são MISS.
"""
from dataclasses import dataclass
import hashlib
import json
import re

from sqlglot import exp, parse, parse_one

from app.agent.state.cache_key import build_cache_key

CONTRACT = "explicit-global-monthly-v1"
_METRICS = {
    "valores faturados": "receita_total",
    "receitas de energia": "receita_energia",
    "consumos de energia": "consumo_total_kwh",
}
# Período e perspectiva são obrigatórios: não herdar filtros/datas da conversa.
_RANKING = re.compile(
    r"quais (?:são )?os (?P<n>[1-9]|[12][0-9]|30|três) meses com "
    r"(?P<direction>maiores|menores) "
    r"(?P<metric>valores faturados|receitas de energia|consumos de energia) "
    r"em todo o histórico da distribuidora, sem filtros adicionais\??", re.IGNORECASE,
)


def resolve_intent(question: str) -> dict | None:
    match = _RANKING.fullmatch(question)
    if match is None:
        return None
    count = match['n'].lower()
    return {
        "contract": CONTRACT, "metric": _METRICS[match['metric'].lower()],
        "operation": "ranking", "grain": "month", "period": "all_snapshot",
        "scope": "all_distributor", "filters": [], "quantity": 3 if count == "três" else int(count),
        "descending": match['direction'].lower() == "maiores",
    }


def intent_digest(intent: dict) -> str:
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class CacheEligibility:
    intent_hash: str
    sql_hash: str
    contract: str = CONTRACT

    def metadata(self):
        return {"contract": self.contract, "intent_hash": self.intent_hash, "sql_hash": self.sql_hash}


def prove_independence(question: str, sql: str | None) -> CacheEligibility | None:
    intent = resolve_intent(question)
    if intent is None or sql is None:
        return None
    try:
        statements = parse(sql, read="sqlite")
        if len(statements) != 1:
            return None
        candidate = statements[0]
        if not isinstance(candidate, exp.Select) or any(node.comments for node in candidate.walk()):
            return None
        # Alias também pode carregar informação herdada. Aceitar só nomes neutros
        # do contrato, nunca um rótulo livre que possa depender da conversa.
        permitted = [
            {"mes_referencia", "mes"},
            {intent["metric"], "total", "soma"} | ({"valor_faturado"} if intent["metric"] == "receita_total" else set()),
        ]
        if len(candidate.expressions) != 2:
            return None
        for index, projection in enumerate(candidate.expressions):
            if isinstance(projection, exp.Alias) and projection.alias.lower() not in permitted[index]:
                return None
        aliases = {projection.alias: projection.this.copy() for projection in candidate.expressions if isinstance(projection, exp.Alias)}
        for ordered in candidate.find_all(exp.Ordered):
            value = ordered.this
            if isinstance(value, exp.Column) and not value.table and value.name in aliases:
                ordered.set("this", aliases[value.name].copy())
        candidate.set("expressions", [projection.this.copy() if isinstance(projection, exp.Alias) else projection for projection in candidate.expressions])
        metric, n = intent['metric'], intent['quantity']
        direction = "DESC" if intent['descending'] else "ASC"
        direct = f"SELECT mes_referencia, {metric} FROM kpis_mensal ORDER BY {metric} {direction} LIMIT {n}"
        grouped = f"SELECT mes_referencia, SUM({metric}) FROM kpis_mensal GROUP BY mes_referencia ORDER BY SUM({metric}) {direction} LIMIT {n}"
        canonical = candidate.sql(dialect="sqlite", normalize=True)
        allowed = [parse_one(text, read="sqlite").sql(dialect="sqlite", normalize=True) for text in (direct, grouped)]
        if canonical not in allowed:
            return None
        return CacheEligibility(intent_hash=intent_digest(intent), sql_hash=hashlib.sha256(canonical.encode()).hexdigest())
    except Exception:
        return None


def independent_lookup_key(question: str, session_id: str, data_version: str, *, user_identity: str | None = None) -> str | None:
    intent = resolve_intent(question)
    if intent is None:
        return None
    return build_cache_key(
        normalized_question=question, session_id=session_id, data_version=data_version,
        memory_context="independent:" + CONTRACT + ":" + intent_digest(intent),
        user_identity=user_identity,
    ) + ":independent"
