import sqlite3
import pytest
from app.agent.schemas import RequestedPeriod, SemanticIntent
from app.agent.semantic_plan import period_problem, use_equivalent_rollup, metric_grain_problem


@pytest.mark.parametrize('year', ['2023','2025','2027'])
def test_year_intent_never_inherits_partial_coverage(year):
    period = RequestedPeriod(granularity='year',start=year+'-01',end=year+'-06',reference='conversation')
    assert period.end==year+'-12'
    intent = SemanticIntent(kind='analytical',resolved_question='Consumo anual',period=period)
    wrong=f"SELECT SUM(consumo_kwh) FROM fato_segmento_mensal WHERE mes_referencia BETWEEN '{year}-01' AND '{year}-06'"
    assert period_problem(intent,wrong)
    assert period_problem(intent,wrong.replace(year+'-06',year+'-12')) is None
    assert period_problem(intent,f"SELECT '{year}-01','{year}-12',SUM(consumo_kwh) FROM fato_segmento_mensal")


@pytest.mark.parametrize('expression', ["AVG(consumo_kwh)", "COUNT(*)", "COUNT(DISTINCT id_uc)", "SUM(DISTINCT consumo_kwh)"])
def test_rollup_does_not_change_non_additive_semantics(expression):
    sql=f'SELECT {expression} FROM fato_consumo_faturamento'
    assert use_equivalent_rollup(sql)==(sql,None)


@pytest.mark.parametrize('suffix', ["WHERE id_uc='x'", "WHERE consumo_kwh>100", "JOIN dim_uc USING(id_uc)"])
def test_rollup_rejects_unsupported_filters_or_grains(suffix):
    sql=f'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento {suffix}'
    assert use_equivalent_rollup(sql)==(sql,None)


def test_rollup_preserves_results_filters_and_order():
    with sqlite3.connect(':memory:') as c:
        c.executescript("""
        CREATE TABLE fato_consumo_faturamento(municipio TEXT,mes_referencia TEXT,consumo_kwh REAL,valor_total REAL);
        INSERT INTO fato_consumo_faturamento VALUES ('A','2025-01',10,7),('A','2025-01',30,11),('B','2025-01',12,8);
        CREATE TABLE fato_segmento_mensal AS SELECT municipio,mes_referencia,SUM(consumo_kwh) AS consumo_kwh,SUM(valor_total) AS receita_total
          FROM fato_consumo_faturamento GROUP BY municipio,mes_referencia;
        """)
        sql="SELECT f.municipio,SUM(f.consumo_kwh),SUM(f.valor_total) AS valor_total FROM fato_consumo_faturamento f WHERE f.mes_referencia='2025-01' GROUP BY f.municipio ORDER BY valor_total DESC"
        optimized,note=use_equivalent_rollup(sql)
        assert note and 'fato_segmento_mensal' in optimized
        assert c.execute(sql).fetchall()==c.execute(optimized).fetchall()


def test_continuity_denominator_must_be_monthly_before_accumulation():
    intent = SemanticIntent(kind='hybrid',resolved_question='Indicador anual',period=RequestedPeriod(
        granularity='year',start='2025-01',end='2025-12',reference='explicit'))
    wrong="SELECT municipio,SUM(qtd_interrupcoes)*1.0/SUM(qtd_ucs_alimentador_mes) FROM dec_fec_alimentador_mensal GROUP BY municipio"
    assert metric_grain_problem(intent,wrong)
    assert metric_grain_problem(intent,"SELECT municipio,SUM(fec) FROM dec_fec_alimentador_mensal GROUP BY municipio")
    correct="SELECT municipio,SUM(fec_mes) FROM (SELECT municipio,mes_referencia,SUM(qtd_interrupcoes)*1.0/SUM(qtd_ucs_alimentador_mes) AS fec_mes FROM dec_fec_alimentador_mensal GROUP BY municipio,mes_referencia) GROUP BY municipio"
    assert metric_grain_problem(intent,correct) is None


def test_ambiguity_is_clarification_not_a_provider_failure():
    from app.agent.schemas import InterpretedRequest
    plan=InterpretedRequest(status='ready',sql='SELECT SUM(receita_total) FROM kpis_mensal',
        interpretation=SemanticIntent(kind='analytical',resolved_question='Valor?',ambiguities=['Métrica não definida']))
    assert plan.status.value=='needs_clarification' and plan.sql is None
    assert 'Métrica não definida' in plan.reason


def test_hybrid_concept_draft_is_not_a_provider_protocol_error():
    from app.agent.schemas import InterpretedRequest
    plan=InterpretedRequest(status='ready',sql='SELECT SUM(qtd_interrupcoes) FROM dec_fec_alimentador_mensal',
        interpretation=SemanticIntent(kind='hybrid',resolved_question='Explique e consulte',source_ids=['dominio.continuidade']),
        knowledge_answer='Rascunho conceitual, ainda não aprovado pela validação de saída.')
    assert plan.status.value=='ready'
