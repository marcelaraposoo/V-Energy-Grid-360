"""Caracterização do risco pós-SQL. Sem Redis, rede ou alteração de produção."""
import ast
import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.agent import pipeline, sql_generator, answer_synthesizer, sql_execution_orchestrator
from app.agent.schemas import (
    AgentOutcome, MemoryEntry, SQLGenerationResult, SQLGenerationStatus,
    SynthesisResult, SynthesisStatus,
)
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.sql_cache import PlanLookup, sql_cache_plan

QUESTION = "Qual o consumo por classe?"
SQL = "SELECT classe, SUM(consumo_kwh) AS total FROM dim_uc GROUP BY classe ORDER BY total DESC"


class Cache:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return None  # Isola o segundo lookup, depois da C4.2 real.

    async def set_approved(self, key, value, ttl, *, plan, independent=None):
        self.values[plan.lookup] = (plan.digest, value.model_copy(deep=True))

    async def get_plan(self, key, *, digest):
        item = self.values.get(key)
        return PlanLookup(item[1].model_copy(deep=True), "hit") if item and item[0] == digest else PlanLookup(None, "not_found_or_expired")


class Memory:
    def __init__(self):
        self.entries = []

    async def get_context(self, session):
        return list(self.entries)

    async def append(self, session, entry):
        self.entries.append(entry)


@pytest.fixture
def harness(monkeypatch, tmp_path):
    db = tmp_path / "synthetic.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE dim_uc(classe TEXT, consumo_kwh REAL)")
        connection.executemany("INSERT INTO dim_uc VALUES (?, ?)", [("RESIDENCIAL", 100), ("COMERCIAL", 50)])
    current = {}
    calls = {"generation": [], "synthesis": [], "execution": []}
    memory = Memory()
    audit = AsyncMock()
    cache = Cache()

    async def generate(prompt, **kwargs):
        calls["generation"].append(prompt)
        return SQLGenerationResult(status=SQLGenerationStatus.READY, sql=current["sql"]), [], None

    async def synthesize(prompt, **kwargs):
        calls["synthesis"].append(prompt)
        answer = "O consumo é 100 kWh." if "classe = 'RESIDENCIAL'" in prompt else "Os consumos são 100 e 50 kWh."
        return SynthesisResult(status=SynthesisStatus.ANSWERED, answer=answer, assumptions=["Dados do snapshot."]), [], None

    original_execute = sql_execution_orchestrator.execute_sql
    def execute(sql, **kwargs):
        calls["execution"].append(sql)
        return original_execute(sql, **kwargs)

    monkeypatch.setattr(sql_generator, "run_with_fallback", generate)
    monkeypatch.setattr(answer_synthesizer, "run_with_fallback", synthesize)
    monkeypatch.setattr(sql_execution_orchestrator, "execute_sql", execute)
    monkeypatch.setattr(pipeline, "load_database_context", lambda: "Schema sintético de dim_uc.")

    def ask(context, *, sql=SQL, use_cache=True, session="same-session", version="snapshot-v1"):
        memory.entries = [MemoryEntry(question="Contexto anterior sintético", answer=context, outcome=AgentOutcome.ANSWERED)]
        current["sql"] = sql
        deps = AgentStateDependencies(cache_store=cache if use_cache else None, memory_store=memory, audit_store=audit, data_version=version)
        result = asyncio.run(pipeline.answer_question(QUESTION, session_id=session, database_path=str(db), state_dependencies=deps))
        assert result.outcome == AgentOutcome.ANSWERED
        return result

    return ask, calls, audit


def payload(result):
    return result.message, result.assumptions, result.visualization


def test_different_histories_same_raw_sql_hit_preserves_approved_payload(harness):
    ask, calls, audit = harness
    first = ask("MARCADOR_CONTEXTO_UM: conversa sobre distribuição residencial.")
    second = ask("MARCADOR_CONTEXTO_DOIS: conversa sobre distribuição comercial.")
    assert not first.cache_hit and second.cache_hit
    assert payload(first) == payload(second)
    assert len(calls["generation"]) == 2
    assert len(calls["synthesis"]) == len(calls["execution"]) == 1
    assert calls["generation"][0] != calls["generation"][1]
    assert all("MARCADOR_CONTEXTO" not in prompt for prompt in calls["synthesis"])
    assert audit.save.await_count == 2 and audit.save.await_args.args[0].cache_hit


def test_without_cache_different_histories_have_identical_synthesis_inputs(harness):
    ask, calls, _ = harness
    first = ask("MARCADOR_CONTEXTO_UM", use_cache=False)
    second = ask("MARCADOR_CONTEXTO_DOIS", use_cache=False)
    assert payload(first) == payload(second)
    assert calls["synthesis"][0] == calls["synthesis"][1]
    assert calls["generation"][0] != calls["generation"][1]


@pytest.mark.parametrize("overrides", [
    {"session": "other-session"}, {"version": "snapshot-v2"},
    {"sql": SQL.replace("FROM dim_uc", "FROM dim_uc WHERE classe = 'RESIDENCIAL'")},
])
def test_changed_scope_or_resolved_reference_does_not_hit(harness, overrides):
    ask, calls, _ = harness
    ask("Primeiro contexto sintético.")
    second = ask("Outro contexto sintético.", **overrides)
    assert not second.cache_hit and len(calls["execution"]) == 2


def test_alias_equivalence_can_reuse_different_presentation_metadata(harness):
    ask, _, _ = harness
    renamed = SQL.replace("AS total", "AS consumo_kwh").replace("ORDER BY total", "ORDER BY consumo_kwh")
    assert sql_cache_plan(QUESTION, SQL, "s", "v") == sql_cache_plan(QUESTION, renamed, "s", "v")
    original = ask("Contexto sintético inicial.")
    cached = ask("Outro contexto sintético.", sql=renamed)
    control = ask("Outro contexto sintético.", sql=renamed, use_cache=False)
    assert cached.cache_hit and payload(cached) == payload(original)
    assert cached.message == control.message and cached.assumptions == control.assumptions
    assert cached.visualization.points == control.visualization.points
    assert cached.visualization.title != control.visualization.title
    assert cached.visualization.unit is None and control.visualization.unit == "kWh"


def test_old_reproducer_stub_bypasses_post_sql_lookup():
    path = Path(__file__).resolve().parents[1] / "manual/reproduce_consecutive_cache_miss.py"
    module = ast.parse(path.read_text(encoding="utf-8-sig"))
    script = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCRIPT" for t in node.targets))
    tree = ast.parse(script)
    generate = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == "generate")
    from app.agent import schemas
    namespace = dict(vars(schemas), calls={"sql_flow": 0}, sql=SQL, result=schemas.QueryExecutionResult(columns=["total"], rows=[[7]], row_count=1))
    exec(compile(ast.Module(body=[generate], type_ignores=[]), str(path), "exec"), namespace)
    callback = AsyncMock()
    flow = asyncio.run(namespace["generate"](cache_lookup=callback))
    callback.assert_not_awaited()
    assert flow.executed and flow.cached_response is None
