import sqlite3
import pytest
from app.agent.aggregate_query import optimize_consumption


@pytest.mark.parametrize('suffix',[
    '', " WHERE municipio='M1'", " WHERE mes_referencia BETWEEN '2026-01' AND '2026-02'", " WHERE classe='C1' AND bairro='B1'",
])
def test_aggregate_rewrite_is_equivalent_for_supported_filters(suffix):
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE fato_consumo_faturamento(mes_referencia TEXT,municipio TEXT,bairro TEXT,classe TEXT,consumo_kwh REAL)')
        c.executemany('INSERT INTO fato_consumo_faturamento VALUES (?,?,?,?,?)',[('2026-01','M1','B1','C1',10),('2026-01','M1','B1','C1',20),('2026-02','M2','B2','C2',50)])
        c.execute('CREATE TABLE fato_segmento_mensal AS SELECT mes_referencia,municipio,bairro,classe,SUM(consumo_kwh) consumo_kwh FROM fato_consumo_faturamento GROUP BY mes_referencia,municipio,bairro,classe')
        sql='SELECT municipio,SUM(consumo_kwh) AS consumo FROM fato_consumo_faturamento'+suffix+' GROUP BY municipio ORDER BY consumo DESC LIMIT 3'
        optimized=optimize_consumption(sql)
        assert 'fato_segmento_mensal' in optimized
        assert c.execute(sql).fetchall()==c.execute(optimized).fetchall()


@pytest.mark.parametrize('sql',[
    'SELECT COUNT(*) FROM fato_consumo_faturamento',
    'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento WHERE id_uc=1',
    'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento WHERE consumo_kwh>10',
    'SELECT AVG(consumo_kwh) FROM fato_consumo_faturamento',
    'SELECT SUM(DISTINCT consumo_kwh) FROM fato_consumo_faturamento',
    'SELECT municipio,consumo_kwh FROM fato_consumo_faturamento',
    'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento JOIN dim_uc USING(id_uc)',
    'SELECT SUM(consumo_kwh) FROM fato_consumo_faturamento; SELECT 1',
])
def test_unsupported_grains_filters_and_operations_preserve_original(sql):
    assert optimize_consumption(sql)==sql
