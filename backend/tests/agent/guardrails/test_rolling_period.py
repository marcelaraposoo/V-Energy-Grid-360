import pytest
from app.agent.guardrails.output_guardrail import validate_output
from app.agent.schemas import QueryExecutionResult,OutputGuardrailDecision


@pytest.mark.parametrize('column,measure',[('dec_12m_horas','DEC'),('fec_12m','FEC')])
def test_period_number_is_grounded_in_published_indicator(column,measure):
    result=QueryExecutionResult(columns=['alimentador','total'],rows=[['AL1',43.9]],row_count=1)
    sql=f"SELECT alimentador,SUM({column}) AS total FROM dec_fec_alimentador_mensal WHERE mes_referencia='2026-06' GROUP BY alimentador"
    guard=validate_output(answer=f'{measure} acumulado nos últimos 12 meses: 43,9.',assumptions=[],question='Ranking?',sql=sql,result=result)
    assert guard.decision==OutputGuardrailDecision.ALLOW


@pytest.mark.parametrize('answer,sql',[
 ('DEC: 12 horas.','SELECT dec_12m_horas AS total FROM dec_fec_alimentador_mensal'),
 ('DEC acumulado em 6 meses: 43,9.','SELECT dec_12m_horas AS total FROM dec_fec_alimentador_mensal'),
 ('DEC acumulado em 12 meses: 43,9.','SELECT dec_horas AS total FROM dec_fec_alimentador_mensal'),
 ('DEC acumulado em 12 meses: 43,9.','SELECT 43.9 AS total FROM dim_uc'),
])
def test_period_exception_cannot_approve_other_claims(answer,sql):
    guard=validate_output(answer=answer,assumptions=[],question='Últimos 12 meses?',sql=sql,result=QueryExecutionResult(columns=['total'],rows=[[43.9]],row_count=1))
    assert guard.decision==OutputGuardrailDecision.BLOCK
