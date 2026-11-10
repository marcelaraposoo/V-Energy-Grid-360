import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock, Mock

import pytest

from app.agent.context.place_search import discover_neighborhoods, neighborhood_candidates
from app.agent.context.runtime import build_runtime_context
from app.agent.context.geography import clarify_geography, resolve_geography
from app.agent.schemas import SemanticIntent, SQLGenerationResult


PLACES = [
    ('Abreu e Lima', 'Caetés I'), ('Abreu e Lima', 'Caetés II'),
    ('Abreu e Lima', 'Caetés III'), ('Abreu e Lima', 'Jardim Caetés'),
    ('Paulista', 'Artur Lundgren I'), ('Paulista', 'Artur Lundgren II'),
    ('Paulista', 'Maranguape I'), ('Paulista', 'Maranguape II'),
    ('Paulista', 'Jardim Maranguape'), ('Paulista', 'Engenho Maranguape'),
    ('Ipojuca', 'Enseada de Serrambi'), ('Ipojuca', 'Ponta de Serrambi'),
    ('Recife', 'Macaxeira'), ('Ilha de Itamaracá', 'Engenho Macaxeira'),
    ('Recife', 'Curado'), ('Jaboatão dos Guararapes', 'Curado'),
    ('Jaboatão dos Guararapes', 'Prazeres'), ('Recife', 'Água Fria'),
    ('Ipojuca', 'Camela Centro'), ('Ipojuca', 'Rurópolis de Camela'),
    ('Ipojuca', 'Distrito Industrial de Ipojuca - Suape'),
    ('Cabo de Santo Agostinho', 'Zona Industrial de Suape'),
]


@pytest.fixture
def gold(tmp_path):
    path = tmp_path / 'gold.db'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE dim_uc(municipio TEXT, bairro TEXT)')
        con.executemany('INSERT INTO dim_uc VALUES (?, ?)', PLACES)
        con.execute('CREATE TABLE kpis_mensal(mes_referencia TEXT)')
        con.execute("INSERT INTO kpis_mensal VALUES ('2026-06')")
    return str(path)


def intent(name, kind='bairro', municipality=None):
    locations = [dict(kind=kind, name=name)]
    if municipality:
        locations.append(dict(kind='municipio', name=municipality))
    return SemanticIntent(kind='analytical', resolved_question='Consumo da localidade', locations=locations)


@pytest.mark.parametrize('name,count', [('caetes',4), ('Maranguape',4), ('Artur Lundgren',2), ('Serrambi',2), ('Camela',2), ('Suape',2)])
def test_partial_names_are_cadastral_options_not_exact_matches(name, count):
    exact, partial = discover_neighborhoods(f'Qual o consumo de {name}?', PLACES)
    assert exact == []
    assert len(partial) == 1
    assert len(partial[0]['opcoes']) == count
    assert len(neighborhood_candidates(name, PLACES)) == count


def test_large_candidate_message_is_visible_and_does_not_become_generic_fallback():
    from app.agent.context.place_search import candidate_message
    from app.agent.pipeline import _is_safe_clarification
    names = ['Alto da Conquista (Bonança)', "Alto do Pau D'arco (Bonança)", 'Bonança I (Bonança)',
             'Bonança II (Bonança)', 'Jardim Massaranduba (Bonança)', 'Monte Sinai (Bonança)',
             'Novo Horizonte (Bonança)', 'Várzea da Cruz (Bonança)']
    message = candidate_message([('Moreno',n) for n in names])
    assert _is_safe_clarification(message)
    assert all(name in message for name in names)
    limited = candidate_message([(f'Município de nome longo {i}',f'Bairro com nome longo {i}') for i in range(40)])
    assert _is_safe_clarification(limited) and 'Há outras opções' in limited


@pytest.mark.parametrize('name', ['Caetés I', 'Caetés II', 'Artur Lundgren II', 'Macaxeira', 'Prazeres'])
def test_full_names_precede_overlapping_fragments(name):
    exact, partial = discover_neighborhoods(f'Consumo do bairro {name}', PLACES)
    assert len(exact) == 1 and exact[0]['bairro'] == name
    assert partial == []


def test_whole_words_not_character_prefixes_or_geographic_markers():
    assert discover_neighborhoods('Qual o consumo do bairro?', PLACES) == ([], [])
    assert neighborhood_candidates('Caeté', PLACES) == []
    assert neighborhood_candidates('I', PLACES) == []
    assert discover_neighborhoods('Consumo de Itamaracá?', PLACES) == ([], [])


def test_runtime_separates_candidates_and_exact_names(gold):
    raw = build_runtime_context('Consumo de CAETES?', gold)
    data = json.loads(raw.split('<metadados_consultados>')[1].split('</')[0])
    assert data['bairros_mencionados'] == []
    assert len(data['bairros_candidatos'][0]['opcoes']) == 4
    assert not data['catalogo_parcial']


def test_partial_discovery_is_bounded_and_reports_truncation(gold):
    with sqlite3.connect(gold) as con:
        con.executemany('INSERT INTO dim_uc VALUES (?, ?)', [('Recife',f'Conjunto Número {i}') for i in range(40)])
    raw = build_runtime_context('Consumo do Conjunto?', gold)
    data = json.loads(raw.split('<metadados_consultados>')[1].split('</')[0])
    assert sum(len(c['opcoes']) for c in data['bairros_candidatos']) == 30
    assert data['catalogo_parcial']


@pytest.mark.parametrize('kind', ['bairro','municipio'])
def test_clarification_surfaces_real_options_even_if_model_misclassifies_kind(gold, kind):
    result = clarify_geography(intent('Caetés',kind),gold,'Qual o consumo de caetés?')
    assert result.status == 'candidates'
    assert all(b in result.message for m,b in PLACES if m=='Abreu e Lima')
    assert 'Abreu e Lima' in result.message


def test_single_partial_option_still_requires_confirmation(gold):
    result = resolve_geography("SELECT municipio FROM dim_uc WHERE bairro='Agua'",intent('Água'),gold,'Consumo de Água?')
    assert result.status == 'candidates' and 'Água Fria' in result.message


@pytest.mark.parametrize('sql', [
    "SELECT municipio FROM dim_uc WHERE bairro='Caetés I'",
    "SELECT municipio FROM dim_uc WHERE bairro IN ('Caetés I','Caetés II','Caetés III')",
    "SELECT municipio FROM dim_uc WHERE bairro LIKE '%Caetés%'",
])
def test_partial_name_never_silently_selects_or_aggregates_candidates(gold, sql):
    result=resolve_geography(sql,intent('Caetés'),gold,'Consumo de Caetés?')
    assert result.status=='candidates' and result.message


def test_invented_completion_of_intent_gets_options_instead_of_execution(gold):
    result=resolve_geography("SELECT municipio FROM dim_uc WHERE bairro='Caetés I'",intent('Caetés I'),gold,'Consumo de Caetés?')
    assert result.status=='candidates' and 'Jardim Caetés' in result.message


def test_duplicate_full_name_requires_municipality_unless_explicitly_selected(gold):
    result=clarify_geography(intent('Curado'),gold,'Consumo do Curado?')
    assert 'Recife' in result.message and 'Jaboatão dos Guararapes' in result.message
    selected=intent('Curado',municipality='Recife')
    result=resolve_geography("SELECT municipio FROM dim_uc WHERE bairro='Curado' AND municipio='Recife'",selected,gold,'Consumo do Curado em Recife?')
    assert result.status=='available' and result.message is None


def test_uncovered_municipality_is_not_replaced_by_neighborhood(gold):
    assert clarify_geography(intent('Caruaru','municipio'),gold,'Consumo de Caruaru?') is None
    result=resolve_geography("SELECT municipio FROM dim_uc WHERE municipio='Caruaru'",intent('Caruaru','municipio'),gold,'Consumo de Caruaru?')
    assert result.status=='not_covered'


@pytest.mark.parametrize('status', ['needs_clarification', 'insufficient_context'])
def test_early_clarification_is_enriched_without_sql_execution_or_extra_model_call(gold,monkeypatch,status):
    from app.agent import sql_execution_orchestrator as flow
    plan=SQLGenerationResult(status=status,reason='Qual localidade?',interpretation=intent('Caetés','municipio'))
    provider=AsyncMock(return_value=(plan,[],None))
    execute=Mock(side_effect=AssertionError('Não consultar consumo sem confirmação'))
    monkeypatch.setattr(flow,'generate_sql',provider)
    monkeypatch.setattr(flow,'execute_sql',execute)
    result=asyncio.run(flow.generate_validate_and_execute('Consumo de Caetés?','schema',database_path=gold))
    assert not result.executed and result.sql is None
    assert result.generation_status.value == 'needs_clarification'
    assert 'Jardim Caetés' in result.generation_reason
    assert result.entity_resolution.startswith('candidates')
    assert provider.await_count==1 and execute.call_count==0


def test_clarification_catalog_failure_is_technical(gold,monkeypatch,tmp_path):
    from app.agent import sql_execution_orchestrator as flow
    plan=SQLGenerationResult(status='needs_clarification',reason='Qual localidade?',interpretation=intent('Caetés'))
    monkeypatch.setattr(flow,'generate_sql',AsyncMock(return_value=(plan,[],None)))
    result=asyncio.run(flow.generate_validate_and_execute('Consumo de Caetés?','schema',database_path=str(tmp_path/'absent.db')))
    assert result.entity_resolution=='technical_failure'
    assert result.outcome.error_type.value=='database_unavailable'
