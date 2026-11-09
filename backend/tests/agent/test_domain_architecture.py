"""Contratos de execução; compreensão linguística é medida no benchmark opt-in."""
import asyncio
import sqlite3
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agent import pipeline, sql_generator, answer_synthesizer
from app.agent.context.geography import resolve_geography
from app.agent.context.knowledge import source_text, sources
from app.agent.schemas import InterpretedRequest, SemanticIntent, SynthesisResult, MemoryEntry
from app.agent.state.dependencies import AgentStateDependencies
from app.agent.state.cache import serialize_cache_value, deserialize_cache_value


class Cache:
    def __init__(self):
        self.data = {}
        self.now = 0

    async def get(self, key):
        item = self.data.get(key)
        return deserialize_cache_value(item[0]) if item and item[1] > self.now else None

    async def set(self, key, value, ttl_seconds):
        self.data[key] = (serialize_cache_value(value), self.now + ttl_seconds)


class Memory:
    def __init__(self):
        self.data = {}

    async def get_context(self, session_id):
        return self.data.get(session_id, [])[-20:]

    async def append(self, session_id, entry):
        self.data.setdefault(session_id, []).append(entry)


def intent(kind="analytical", **kwargs):
    return SemanticIntent(kind=kind, resolved_question="Consumo total em Recife no histórico", **kwargs)


@pytest.fixture
def gold(tmp_path):
    path = tmp_path / "gold.db"
    with sqlite3.connect(path) as con:
        con.executescript("""
        CREATE TABLE dim_uc(municipio TEXT,bairro TEXT);
        INSERT INTO dim_uc VALUES ('Recife','Macaxeira'),('Recife','Centro'),
          ('Olinda','Centro'),('Jaboatão dos Guararapes','Piedade');
        CREATE TABLE kpis_mensal(mes_referencia TEXT);
        INSERT INTO kpis_mensal VALUES ('2026-01'),('2026-06');
        CREATE TABLE fato_segmento_mensal(municipio TEXT, mes_referencia TEXT,consumo_kwh REAL);
        INSERT INTO fato_segmento_mensal VALUES ('Recife','2026-01',120),('Olinda','2026-01',30);
        """)
    return str(path)


@pytest.fixture
def state():
    return AgentStateDependencies(memory_store=Memory(), cache_store=Cache(), data_version="gold-test",
                                  audit_store=type("Audit", (), {"save": AsyncMock()})())


def ask(question, gold, state, session="s"):
    return asyncio.run(pipeline.answer_question(question, database_path=gold,
                                                session_id=session, state_dependencies=state))


def install_analytics(monkeypatch, kind="analytical", sources_ids=(), uses_context=False):
    plan = InterpretedRequest(status="ready", sql="SELECT SUM(consumo_kwh) AS consumo FROM fato_segmento_mensal WHERE municipio='Recife'",
                             interpretation=intent(kind, locations=[{"kind":"municipio", "name":"Recife"}], source_ids=list(sources_ids), uses_context=uses_context))
    generator = AsyncMock(return_value=(plan, [], None))
    synthesis = AsyncMock(return_value=(SynthesisResult(status="answered", answer="O consumo foi de 120 kWh."), [], None))
    monkeypatch.setattr(sql_generator, "run_with_fallback", generator)
    monkeypatch.setattr(answer_synthesizer, "run_with_fallback", synthesis)
    return generator, synthesis


def test_identical_repeat_uses_recorded_context_and_no_providers(monkeypatch, gold, state):
    generator, synthesis = install_analytics(monkeypatch)
    first = ask("Quanto consumiu Recife?", gold, state)
    second = ask("Quanto consumiu Recife?", gold, state)
    assert first.outcome.value == second.outcome.value == "answered"
    assert not first.cache_hit and second.cache_hit
    assert generator.await_count == synthesis.await_count == 1
    assert second.sql == first.sql
    assert len(state.memory_store.data["s"]) == 1
    assert state.memory_store.data["s"][0].context_recorded
    assert next(step for step in second.audit_steps if step.code == "C4.3").status.value == "skipped"


@pytest.mark.parametrize("change", ["period", "city", "question", "context", "session", "version", "expiry", "altered_answer"])
def test_replay_boundaries(monkeypatch, gold, state, change):
    generator, _ = install_analytics(monkeypatch)
    question = "Consumo de Recife em 2026?"
    ask(question, gold, state)
    session = "s"
    if change == "period": question = "Consumo de Recife em 2025?"
    if change == "city": question = "Consumo de Olinda em 2026?"
    if change == "question": question = "Receita de Recife em 2026?"
    if change == "context":
        state.memory_store.data["s"].append(MemoryEntry(question="Apenas residencial", answer="Filtro aplicado.", outcome="answered"))
    if change == "session": session = "other"
    if change == "version": state = replace(state, data_version="gold-next")
    if change == "expiry": state.cache_store.now = 86401
    if change == "altered_answer": state.memory_store.data["s"][-1].answer = "Outra resposta"
    assert not ask(question, gold, state, session).cache_hit
    assert generator.await_count == 2


def test_contextual_retry_preserves_the_original_antecedent(monkeypatch, gold, state):
    generator, _ = install_analytics(monkeypatch, uses_context=True)
    state.memory_store.data["s"] = [MemoryEntry(question="Recife em 2026", answer="120 kWh", outcome="answered")]
    ask("E no ano anterior?", gold, state)
    first_prompt = generator.await_args.args[0]
    assert "Recife em 2026" in first_prompt
    assert ask("E no ano anterior?", gold, state).cache_hit
    state.cache_store.now = 86401
    ask("E no ano anterior?", gold, state)
    assert generator.await_args.args[0] == first_prompt


def test_legacy_or_truncated_history_is_not_reconstructed(monkeypatch, gold, state):
    generator, _ = install_analytics(monkeypatch)
    ask("Consumo?", gold, state)
    state.memory_store.data["s"] = [MemoryEntry(question="Consumo?",answer="120 kWh",outcome="answered") for _ in range(20)]
    assert not ask("Consumo?", gold, state).cache_hit
    assert generator.await_count == 2


def test_memory_failure_does_not_reuse_context_dependent_answer(monkeypatch, gold, state):
    generator, _ = install_analytics(monkeypatch)
    ask("Consumo?", gold, state)
    state.memory_store.get_context = AsyncMock(side_effect=ConnectionError)
    assert not ask("Consumo?", gold, state).cache_hit
    assert generator.await_count == 2


def test_knowledge_has_sources_no_sql_and_is_cacheable(monkeypatch, gold, state):
    plan = InterpretedRequest(status="knowledge", interpretation=intent("conceptual", source_ids=["dominio.continuidade"]),
                             knowledge_answer="DEC mede a duração média sem fornecimento por unidade consumidora, em horas.")
    provider = AsyncMock(return_value=(plan, [], None))
    monkeypatch.setattr(sql_generator, "run_with_fallback", provider)
    forbidden = AsyncMock(side_effect=AssertionError("Sem síntese adicional"))
    monkeypatch.setattr(pipeline, "synthesize_and_validate", forbidden)
    first = ask("Me explica o indicador de duração por unidade", gold, state)
    assert first.outcome.value == "answered" and first.sql is None
    assert first.source_ids == ("dominio.continuidade",)
    second = ask("Me explica o indicador de duração por unidade", gold, state)
    assert second.cache_hit and second.source_ids == first.source_ids
    assert provider.await_count == 1 and forbidden.await_count == 0


def test_hybrid_synthesis_receives_only_selected_document_evidence(monkeypatch, gold, state):
    _, synthesis = install_analytics(monkeypatch, "hybrid", ["dominio.energia"])
    result = ask("Explique consumo e mostre o valor de Recife", gold, state)
    assert result.outcome.value == "answered" and result.source_ids == ("dominio.energia",)
    prompt = synthesis.await_args.args[0]
    assert "quilowatt-hora" in prompt and "DEC é" not in prompt
    assert '120' in prompt


@pytest.mark.parametrize('corrects', [True, False])
def test_documentary_output_has_one_bounded_correction_and_still_fails_closed(monkeypatch, gold, state, corrects):
    bad = InterpretedRequest(status='knowledge',
        interpretation=intent('conceptual', source_ids=['dominio.continuidade']),
        knowledge_answer='O indicador registra 987654 interrupções.')
    good = bad.model_copy(update={'knowledge_answer': 'FEC expressa a frequência média de interrupções por unidade consumidora.'})
    provider = AsyncMock(side_effect=[(bad, [], None), (good if corrects else bad, [], None)])
    monkeypatch.setattr(sql_generator, 'run_with_fallback', provider)
    result = ask('Como funciona o indicador de frequência?', gold, state)
    assert result.outcome.value == ('answered' if corrects else 'output_blocked')
    assert result.sql is None and result.regenerations == 1 and provider.await_count == 2
    assert 'fontes autorizadas' in provider.await_args.args[0]
    assert '# 10. `fato_segmento_mensal`' not in provider.await_args.args[0]
    assert '<metadados_consultados>' not in provider.await_args.args[0]
    if not corrects:
        assert '987654' not in result.message


@pytest.mark.parametrize("name", ["recife", "  RECIFE  ", "JABOATAO   DOS GUARARAPES"])
def test_geography_normalizes_only_cadastral_equivalence(gold, name):
    sql = "SELECT municipio FROM dim_uc WHERE municipio='" + name + "'"
    result = resolve_geography(sql, intent(locations=[{"kind":"municipio", "name":name}]), gold)
    assert result.status == "available" and result.message is None
    with sqlite3.connect(gold) as con:
        assert con.execute(result.sql).fetchall()


@pytest.mark.parametrize("name,kind,status", [("Recif","municipio","suggestion"), ("Caruaru","municipio","not_covered"),
                                             ("Centro","bairro","ambiguous"), ("Macaxeira","bairro","available")])
def test_geography_reports_resolution_outcomes(gold, name, kind, status):
    result = resolve_geography(f"SELECT municipio FROM dim_uc WHERE {kind}='{name}'", intent(locations=[{"kind":kind,"name":name}]), gold)
    assert result.status == status


def test_geography_unavailable_is_technical_failure_not_no_data(monkeypatch, tmp_path, state):
    install_analytics(monkeypatch)
    result = ask("Consumo de Recife?", str(tmp_path / "absent.db"), state)
    assert result.outcome.value == "execution_error"
    assert next(s for s in result.audit_steps if s.code == "ENTITIES").detail == "technical_failure"


def test_unique_neighborhood_can_supply_implicit_parent(gold):
    plan=intent(locations=[{'kind':'bairro','name':'Macaxeira'},{'kind':'municipio','name':'Recife'}])
    sql="SELECT municipio FROM dim_uc WHERE municipio='Recife' AND bairro='Macaxeira'"
    assert resolve_geography(sql,plan,gold,'Consumo de Macaxeira?').status=='available'


def test_sql_cannot_change_the_requested_municipality(gold):
    plan=intent(locations=[{'kind':'municipio','name':'Olinda'}])
    sql="SELECT municipio FROM dim_uc WHERE municipio='Recife'"
    assert resolve_geography(sql,plan,gold,'Consumo de Olinda?').status=='unverified_reference'


def test_contract_rejects_knowledge_with_sql_or_no_sources():
    for kwargs in [dict(sql="SELECT 1", source_ids=["dominio.uc"]), dict(sql=None, source_ids=[])]:
        with pytest.raises(ValidationError):
            InterpretedRequest(status="knowledge", sql=kwargs["sql"], knowledge_answer="Texto",
                               interpretation=intent("conceptual",source_ids=kwargs["source_ids"]))


def test_unknown_sources_fail_closed(monkeypatch):
    plan = InterpretedRequest(status="knowledge", interpretation=intent("conceptual",source_ids=["invento"]),knowledge_answer="Inventado")
    monkeypatch.setattr(sql_generator,"run_with_fallback",AsyncMock(return_value=(plan,[],None)))
    result, _, error = asyncio.run(sql_generator.generate_sql("Explique", "schema"))
    assert result is None and error.value == "invalid_output"
    with pytest.raises(ValueError): source_text(["invento"])


def test_compound_ambiguity_is_rechecked_once_without_forcing_a_query(monkeypatch, gold, state):
    plan=InterpretedRequest(status='needs_clarification',reason='Qual medida deseja?',
        interpretation=SemanticIntent(kind='clarification',resolved_question='Explicar e consultar',
            requested_outputs=['Explicação','Valor de referência'],ambiguities=['Referência indefinida']))
    provider=AsyncMock(return_value=(plan,[],None))
    monkeypatch.setattr(sql_generator,'run_with_fallback',provider)
    result=ask('Explique a medida e mostre o valor',gold,state)
    assert result.outcome.value=='needs_clarification' and result.sql is None
    assert provider.await_count==2 and result.regenerations==1


def test_source_retrieval_excludes_unrelated_schema_and_keeps_runtime_metadata():
    from app.agent.context.knowledge import context_for_sources
    from app.agent.context.loader import load_database_context
    context = load_database_context() + '<metadados_consultados>{"data_atual":"2026-11-09"}</metadados_consultados>'
    focused = context_for_sources(context,['dominio.continuidade'])
    assert '# 5. `dec_fec_alimentador_mensal`' in focused
    assert '# 3. `receita_decomposicao`' not in focused
    assert '# 10. `fato_segmento_mensal`' not in focused
    assert '<metadados_consultados>' in focused
    assert len(focused)<len(context)


def test_structured_planner_supports_existing_provider_preference():
    from app.agent.providers.router import supports_preference
    from app.agent.schemas import ProviderName
    assert supports_preference(ProviderName.GEMINI,'configured-model',InterpretedRequest)


def test_all_curated_sources_have_existing_repository_references():
    import hashlib
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    for source in sources().values():
        for path in source["source"].split("; "):
            assert (root / path).exists(), path
            assert hashlib.sha256((root / path).read_bytes()).hexdigest() == source['source_fingerprints'][path], (
                f"A fonte {path} mudou: revise o texto curado e atualize seu fingerprint antes de publicar."
            )
