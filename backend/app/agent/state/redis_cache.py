"""Cache Redis opcional; falhas nunca impedem a resposta do agente."""

import asyncio
import logging
import json
import re

from redis.asyncio import Redis

from app.agent.schemas import PostProcessingResult
from app.agent.state.redis_client import create_redis_client
from app.agent.state.cache import (
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    deserialize_cache_value,
    serialize_cache_value,
    validate_cache_timeout,
    validate_cache_ttl,
)


logger = logging.getLogger(__name__)


# Um índice técnico por escopo limita todas as versões/perguntas da sessão.
# GET não renova TTL. SET + limpeza + limite são uma única operação atômica.
_BOUNDED_SET = """
local bucket = KEYS[2]
local function remove_pointer(member)
    local payload = redis.call('GET', member)
    if payload then
        local ok, envelope = pcall(cjson.decode, payload)
        if ok and type(envelope) == 'table' then
            local plan = envelope.plan
            if type(plan) == 'table' and type(plan.lookup) == 'string' and redis.call('GET', plan.lookup) == member then
                redis.call('DEL', plan.lookup)
            end
            local proof = envelope.eligibility
            if type(proof) == 'table' and type(proof.lookup) == 'string' and redis.call('GET', proof.lookup) == member then
                redis.call('DEL', proof.lookup)
            end
        end
    end
end
remove_pointer(KEYS[1])
for _, member in ipairs(redis.call('ZRANGE', bucket, 0, -1)) do
    if redis.call('EXISTS', member) == 0 then redis.call('ZREM', bucket, member) end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
for i = 3, #KEYS do
    local ttl_ms = redis.call('PTTL', KEYS[1])
    if ttl_ms > 0 then redis.call('SET', KEYS[i], KEYS[1], 'PX', ttl_ms) end
end
local now = redis.call('TIME')
redis.call('ZADD', bucket, tonumber(now[1]) * 1000000 + tonumber(now[2]), KEYS[1])
local excess = redis.call('ZCARD', bucket) - tonumber(ARGV[3])
if excess > 0 then
    local oldest = redis.call('ZRANGE', bucket, 0, excess - 1)
    for _, member in ipairs(oldest) do
        remove_pointer(member)
        redis.call('DEL', member)
        redis.call('ZREM', bucket, member)
    end
end
local ttl = math.max(tonumber(ARGV[2]), redis.call('TTL', bucket))
redis.call('EXPIRE', bucket, ttl)
return 1
"""


_READ_INDEPENDENT = """
local target = redis.call('GET', KEYS[1])
if not target or string.sub(target, 1, string.len(ARGV[1])) ~= ARGV[1] then return nil end
if redis.call('PTTL', KEYS[1]) <= 0 or redis.call('PTTL', target) <= 0 then return nil end
local payload = redis.call('GET', target)
if not payload then return nil end
return {target, payload}
"""


def _decode(payload):
    try:
        raw = json.loads(payload)
        if isinstance(raw, dict) and raw.get("_cache_format") in {"c2-independent-v1", "c2-plan-v1"}:
            if "plan" in raw:
                plan = raw["plan"]
                if (not isinstance(plan, dict) or set(plan) != {"lookup", "digest", "contract"}
                    or any(not isinstance(value, str) for value in plan.values())
                    or re.fullmatch(r"[a-f0-9]{64}", plan["digest"]) is None):
                    return None
            if raw.get("_cache_format") == "c2-plan-v1":
                if set(raw) != {"_cache_format", "plan", "response"}:
                    return None
                return deserialize_cache_value(json.dumps(raw["response"]))
            proof = raw.get("eligibility", {})
            if (set(raw) not in ({"_cache_format", "eligibility", "response"}, {"_cache_format", "eligibility", "response", "plan"})
                or not isinstance(proof, dict)
                or set(proof) != {"lookup", "contract", "intent_hash", "sql_hash"}
                or any(not isinstance(value, str) for value in proof.values())
                or any(re.fullmatch(r"[a-f0-9]{64}", proof[field]) is None for field in ("intent_hash", "sql_hash"))):
                return None
            return deserialize_cache_value(json.dumps(raw["response"]))
        return deserialize_cache_value(payload)
    except (TypeError, ValueError):
        return None


class RedisCacheStore:
    def __init__(
        self, url: str, *, timeout_seconds: float = DEFAULT_CACHE_TIMEOUT_SECONDS,
        max_entries_per_session: int = 100,
    ) -> None:
        validate_cache_timeout(timeout_seconds)
        validate_cache_ttl(max_entries_per_session)
        self._max_entries_per_session = max_entries_per_session
        self._url = url
        self._timeout_seconds = timeout_seconds

    def _client(self) -> Redis:
        # O HTTP atual usa asyncio.run por pergunta: não compartilhar pools
        # entre event loops. O contexto de cada operação fecha seu próprio pool.
        return create_redis_client(self._url, self._timeout_seconds)

    async def get(self, key: str) -> PostProcessingResult | None:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    payload = await client.get(key)
                response = _decode(payload) if payload is not None else None
                from app.agent.state.sql_cache import record_cache
                reason = "hit" if response is not None else ("payload_invalid" if payload is not None else "not_found_or_expired")
                record_cache(reason, "pre_sql", response is not None)
                return response
        except Exception as error:
            from app.agent.state.sql_cache import record_cache
            record_cache("redis_error", "pre_sql")
            logger.warning("Falha Redis GET. error_type=%s", type(error).__name__)
            return None

    async def set(
        self, key: str, value: PostProcessingResult, ttl_seconds: int,
    ) -> None:
        try:
            validate_cache_ttl(ttl_seconds)
            payload = serialize_cache_value(value)
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    bucket = key.rsplit(":", 1)[0] + ":entries"
                    await client.eval(
                        _BOUNDED_SET, 2, key, bucket, payload,
                        ttl_seconds, self._max_entries_per_session,
                    )
        except Exception as error:
            logger.warning("Falha Redis SET. error_type=%s", type(error).__name__)


    async def set_independent(self, key, value, ttl_seconds, *, lookup_key, eligibility):
        """Uma entrada aprovada + ponteiro; TTL e limite na mesma operação Redis."""
        try:
            validate_cache_ttl(ttl_seconds)
            response = json.loads(serialize_cache_value(value))
            scope = key.rsplit(":", 1)[0] + ":"
            if not lookup_key.startswith(scope) or not lookup_key.endswith(":independent"):
                return
            envelope = {"_cache_format": "c2-independent-v1", "response": response,
                        "eligibility": {**eligibility.metadata(), "lookup": lookup_key}}
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    await client.eval(_BOUNDED_SET, 3, key, key.rsplit(":",1)[0]+":entries",
                                      lookup_key, json.dumps(envelope), ttl_seconds, self._max_entries_per_session)
        except Exception as error:
            logger.warning("Falha Redis SET independente. error_type=%s", type(error).__name__)

    async def get_independent(self, lookup_key, *, intent_hash):
        try:
            scope = lookup_key.removesuffix(":independent").rsplit(":", 1)[0] + ":"
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    record = await client.eval(_READ_INDEPENDENT, 1, lookup_key, scope)
            if not record:
                return None
            payload = record[1]
            raw = json.loads(payload)
            proof = raw.get("eligibility", {})
            from app.agent.state.cache_eligibility import CONTRACT
            if (raw.get("_cache_format") != "c2-independent-v1" or proof.get("contract") != CONTRACT
                or proof.get("lookup") != lookup_key or proof.get("intent_hash") != intent_hash):
                return None
            return _decode(payload)
        except Exception as error:
            logger.warning("Falha Redis GET independente. error_type=%s", type(error).__name__)
            return None


    async def set_approved(self, key, value, ttl_seconds, *, plan, independent=None):
        try:
            validate_cache_ttl(ttl_seconds)
            envelope = {"_cache_format": "c2-plan-v1", "plan": plan.metadata(),
                        "response": json.loads(serialize_cache_value(value))}
            pointers = [plan.lookup]
            if independent is not None:
                lookup, proof = independent
                envelope["_cache_format"] = "c2-independent-v1"
                envelope["eligibility"] = {**proof.metadata(), "lookup": lookup}
                pointers.append(lookup)
            scope = key.rsplit(":", 1)[0] + ":"
            if any(not pointer.startswith(scope) for pointer in pointers):
                return
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    await client.eval(_BOUNDED_SET, 2 + len(pointers), key,
                                      key.rsplit(":",1)[0]+":entries", *pointers,
                                      json.dumps(envelope), ttl_seconds, self._max_entries_per_session)
        except Exception as error:
            logger.warning("Falha Redis SET aprovado. error_type=%s", type(error).__name__)

    async def get_plan(self, lookup, *, digest):
        from app.agent.state.sql_cache import PlanLookup, CONTRACT
        try:
            scope = lookup.removesuffix(":plan").rsplit(":", 1)[0] + ":"
            async with asyncio.timeout(self._timeout_seconds):
                async with self._client() as client:
                    record = await client.eval(_READ_INDEPENDENT, 1, lookup, scope)
            if not record:
                return PlanLookup(None, "not_found_or_expired")
            raw = json.loads(record[1])
            proof = raw.get("plan", {})
            if proof != {"lookup": lookup, "digest": digest, "contract": CONTRACT}:
                return PlanLookup(None, "plan_mismatch")
            response = _decode(record[1])
            return PlanLookup(response, "hit" if response is not None else "payload_invalid")
        except (ValueError, TypeError, AttributeError):
            return PlanLookup(None, "payload_invalid")
        except Exception:
            return PlanLookup(None, "redis_error")
