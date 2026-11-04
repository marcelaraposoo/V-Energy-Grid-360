"""Auditoria: somente fixtures sintéticas; xfail descreve lacunas sem mudar C5."""
import sqlite3
import pytest
from app.agent.schemas import AgentOutcome,MemoryEntry,QueryExecutionResult,OutputGuardrailDecision,GuardrailDecision
from app.agent.state.memory_context import build_memory_context
from app.agent.state.memory import should_store_in_memory
from app.agent.sql_generator import build_sql_generation_prompt
from app.agent.guardrails.input_guardrail import validate_input
from app.agent.guardrails.output_guardrail import validate_output
from app.agent.prompts.sql_generation.loader import load_sql_generation_prompts


def test_dec_followup_and_fec_reach_generation_with_valid_anchor_and_clarification():
    initial=MemoryEntry(question='Quais alimentadores tiveram pior DEC nos últimos 12 meses disponíveis?',answer='O ranking DEC considera os alimentadores e o período disponível.',outcome=AgentOutcome.ANSWERED)
    clarification=MemoryEntry(question='E nos últimos 6 meses?',answer='Qual município para consultar interrupções?',outcome=AgentOutcome.NEEDS_CLARIFICATION)
    memory=build_memory_context([initial,clarification])
    prompt=build_sql_generation_prompt('Agora considere o FEC.','Schema sintético.',memory)
    assert initial.question in prompt and clarification.answer in prompt
    assert 'Agora considere o FEC.' in prompt
    # Caracteriza a falta de distinção de status no texto enviado ao modelo.
    assert 'needs_clarification' in memory
    assert should_store_in_memory(AgentOutcome.NEEDS_CLARIFICATION)
    assert not should_store_in_memory(AgentOutcome.PROVIDER_ERROR)


def test_long_answer_can_drop_entire_recent_reference():
    anchor=MemoryEntry(question='Ranking DEC por alimentador.',answer='x'*4100,outcome=AgentOutcome.ANSWERED)
    recent=MemoryEntry(question='E nos últimos 6 meses?',answer='Qual município?',outcome=AgentOutcome.NEEDS_CLARIFICATION)
    memory=build_memory_context([anchor,recent])
    assert anchor.question in memory and recent.question in memory


def test_financial_ambiguity_instruction_already_exists():
    instructions=load_sql_generation_prompts()
    assert 'gastos' in instructions and 'NEEDS_CLARIFICATION' in instructions
    assert 'Uma resposta anterior do assistente não comprova' in instructions


@pytest.mark.parametrize('question',[
    'Quais os 3 municípios com maior consumo?',
    'Quais os 3 municípios com maior consumo? 😊',
])
def test_emoji_does_not_block_legitimate_question(question):
    assert validate_input(question).decision==GuardrailDecision.ALLOW


def test_rolling_indicator_reference_month_is_not_one_month_measure():
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE monthly(month TEXT, dec REAL)')
        c.executemany('INSERT INTO monthly VALUES (?,?)',[(f'2025-{m:02}',1) for m in range(7,13)]+[(f'2026-{m:02}',1) for m in range(1,7)])
        assert c.execute("SELECT SUM(dec) FROM monthly WHERE month BETWEEN '2025-07' AND '2026-06'").fetchone()[0]==12
        assert c.execute("SELECT SUM(dec) FROM monthly WHERE month BETWEEN '2026-01' AND '2026-06'").fetchone()[0]==6
        assert c.execute("SELECT dec FROM monthly WHERE month='2026-06'").fetchone()[0]==1


def test_municipality_and_neighborhood_are_not_interchangeable():
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE uc(id INTEGER, municipio TEXT,bairro TEXT)')
        c.executemany('INSERT INTO uc VALUES (?,?,?)',[(i,'Abreu e Lima',f'Caetés {suffix}') for i,suffix in enumerate(['I','II','III'])])
        assert c.execute("SELECT COUNT(*) FROM uc WHERE municipio='Caetés'").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM uc WHERE bairro LIKE 'Caetés%' AND municipio='Abreu e Lima'").fetchone()[0]==3


@pytest.mark.parametrize('answer',[
    'A receita foi de R$ 10.',
    'O DEC foi de 10 kWh.',
    'Em Olinda, o DEC foi de 10 h.',
])
def test_expected_rejection_of_semantically_incompatible_answer(answer):
    result=QueryExecutionResult(columns=['municipio','dec_horas'],rows=[['Recife',10]],row_count=1)
    decision=validate_output(answer,[],'Qual o DEC em Recife?',"SELECT municipio,dec_horas FROM resumo WHERE municipio='Recife'",result)
    assert decision.decision==OutputGuardrailDecision.BLOCK


def test_expected_rejection_of_swapped_period_values():
    result=QueryExecutionResult(columns=['mes_referencia','total'],rows=[['2025-07',10],['2026-06',20]],row_count=2)
    decision=validate_output('Em julho de 2025 houve 20 ocorrências; em junho de 2026 houve 10.',[], 'Compare julho de 2025 com junho de 2026.','SELECT mes_referencia,total FROM resumo',result)
    assert decision.decision==OutputGuardrailDecision.BLOCK


def test_numbers_without_any_evidence_remain_blocked():
    result=QueryExecutionResult(columns=['total'],rows=[[10]],row_count=1)
    assert validate_output('Há 999 ocorrências.',[],'Quantas ocorrências?','SELECT total FROM resumo',result).decision==OutputGuardrailDecision.BLOCK
