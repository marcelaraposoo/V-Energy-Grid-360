import sqlite3
import pytest
from app.agent.aggregate_query import optimize_consumption
from app.agent.conversation import delta
from app.agent.post_processor import _build_visualization
from app.agent.schemas import QueryExecutionResult


@pytest.mark.parametrize('utterance',['exibe um grafico disso','exiba um gráfico disso','mostra um gráfico disso','mostre um gráfico disso','pode mostrar um gráfico desses dados?'])
def test_natural_chart_requests(utterance):
    assert delta(utterance)==('visualization',None)


def test_three_column_ranking_keeps_identity_values_and_original():
    result=QueryExecutionResult(columns=['alimentador','municipio','dec_12m_horas'],rows=[['A','M1',12.5],['B','M2',8.2]],row_count=2)
    original=result.model_dump()
    chart=_build_visualization(result)
    assert chart and [p.value for p in chart.points]==[12.5,8.2]
    assert [p.label for p in chart.points]==['A / M1','B / M2']
    assert result.model_dump()==original


@pytest.mark.parametrize('columns,rows,truncated',[
 (['alimentador','dec_horas','fec'],[['A',1,2],['B',3,4]],False),
 (['alimentador','municipio','dec_horas'],[['A','M',1],['A','M',2]],False),
 (['alimentador','municipio','dec_horas'],[['A','M',1],['B','N',2]],True),
 (['id_uc','municipio','dec_horas'],[['A','M',1],['B','N',2]],False),
])
def test_ambiguous_or_incomplete_chart_is_not_fabricated(columns,rows,truncated):
    assert _build_visualization(QueryExecutionResult(columns=columns,rows=rows,row_count=2,truncated=truncated)) is None


@pytest.mark.parametrize('condition',['ano=2025','2025=ano','f.ano=2025', "SUBSTR(mes_referencia,1,4)='2025'", "'2025'=SUBSTR(mes_referencia,1,4)"])
def test_year_predicate_rewrite_preserves_result(condition):
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE fato_consumo_faturamento(mes_referencia TEXT,ano INTEGER,municipio TEXT,consumo_kwh REAL)')
        c.executemany('INSERT INTO fato_consumo_faturamento VALUES (?,?,?,?)',[('2025-01',2025,'Recife',10),('2025-12',2025,'Recife',20),('2026-01',2026,'Recife',100),('2025-06',2025,'Outro',200)])
        c.execute('CREATE TABLE fato_segmento_mensal AS SELECT mes_referencia,municipio,SUM(consumo_kwh) consumo_kwh FROM fato_consumo_faturamento GROUP BY mes_referencia,municipio')
        sql=f"SELECT SUM(consumo_kwh) AS consumo FROM fato_consumo_faturamento f WHERE municipio='Recife' AND {condition}"
        optimized=optimize_consumption(sql)
        assert 'fato_segmento_mensal' in optimized and '2025-01' in optimized
        assert c.execute(sql).fetchall()==c.execute(optimized).fetchall()==[(30,)]


@pytest.mark.parametrize('condition',['ano>=2025','ano=2025 AND id_uc=1',"ano='2025'", 'ano=2025 AND consumo_kwh>10', "SUBSTR(mes_referencia,2,4)='2025'", "SUBSTR(mes_referencia,1,4)='202'", "SUBSTR(mes_referencia,1,4)=2025"])
def test_unsupported_year_filters_stay_unchanged(condition):
    sql=f'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento WHERE {condition}'
    assert optimize_consumption(sql)==sql


def test_cached_visualization_remains_available_to_followup(monkeypatch):
    import asyncio
    from app.agent import pipeline
    from app.agent.schemas import PostProcessingResult
    from app.agent.state.dependencies import AgentStateDependencies
    from unittest.mock import AsyncMock
    source=QueryExecutionResult(columns=['alimentador','municipio','dec_12m_horas'],rows=[['A','M',1],['B','N',2]],row_count=2)
    chart=_build_visualization(source)
    cached=PostProcessingResult(answer='Ranking aprovado.',visualization=chart)
    class Memory:
        turns=[]
        async def get_context(self,key):return list(self.turns)
        async def append(self,key,value):self.turns.append(value)
    memory=Memory()
    cache=type('Cache',(),{'get':AsyncMock(return_value=cached),'set':AsyncMock()})()
    deps=AgentStateDependencies(memory_store=memory,cache_store=cache,data_version='v1')
    async def forbidden(*a,**k):pytest.fail('HIT e gráfico referencial não devem executar SQL/LLM')
    monkeypatch.setattr(pipeline,'generate_validate_and_execute',forbidden)
    first=asyncio.run(pipeline.answer_question('Quais alimentadores tiveram pior DEC?',session_id='synthetic',state_dependencies=deps))
    assert first.cache_hit and memory.turns[-1].approved_visualization==chart
    second=asyncio.run(pipeline.answer_question('exibe um grafico disso',session_id='synthetic',state_dependencies=deps))
    assert second.visualization==chart
    cache.set.assert_not_awaited()
