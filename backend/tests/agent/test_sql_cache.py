import pytest
from app.agent.state.sql_cache import sql_cache_plan, canonical_cache_sql
from app.core.telemetry_export import safe_attributes

SQL = "SELECT alimentador, SUM(dec_horas) AS dec FROM dec_fec_alimentador_mensal WHERE mes_referencia BETWEEN '2025-07' AND '2026-06' GROUP BY alimentador ORDER BY dec DESC LIMIT 10"
QUESTION = "Quais alimentadores tiveram pior DEC nos últimos 12 meses?"

def plan(sql=SQL, question=QUESTION, session="s", version="v"):
    return sql_cache_plan(question, sql, session, version)

def test_formatting_only_does_not_change_plan():
    assert plan() == plan(SQL.replace("SELECT", "select").replace(" FROM", "\nFROM"))

@pytest.mark.parametrize("sql", [SQL.replace("dec_horas", "fec"), SQL.replace("2025-07", "2025-08"), SQL.replace("LIMIT 10", "LIMIT 5"), SQL.replace("DESC", "ASC"), SQL.replace("GROUP BY", "AND alimentador = 'AL1' GROUP BY")])
def test_metric_filter_period_order_and_limit_are_part_of_identity(sql):
    assert plan(sql) != plan()

@pytest.mark.parametrize("question,session,version", [("Qual o FEC?","s","v"),(QUESTION,"s2","v"),(QUESTION,"s","v2")])
def test_scope_and_question_are_part_of_identity(question,session,version):
    assert plan(question=question,session=session,version=version).lookup != plan().lookup

@pytest.mark.parametrize("sql", ["SELECT CURRENT_DATE", "SELECT RANDOM()", "SELECT DATE('now')", "SELECT custom_function(alimentador) FROM dec_fec_alimentador_mensal", "SELECT ?", SQL+"; SELECT 1", SQL+" -- private", "SELECT alimentador FROM dec_fec_alimentador_mensal LIMIT 3"])
def test_unresolved_clock_unknown_functions_and_incomplete_plans_are_not_cached(sql):
    assert canonical_cache_sql(sql) is None
    assert plan(sql) is None

def test_different_physical_metric_recipes_are_not_assumed_equivalent():
    rolling = "SELECT alimentador, dec_12m_horas AS dec FROM dec_fec_alimentador_mensal WHERE mes_referencia = '2026-06' ORDER BY dec DESC LIMIT 10"
    assert plan(rolling) != plan()

def test_only_closed_cache_categories_can_be_exported():
    attrs = safe_attributes({"cache_reason":"PRIVATE_SQL", "cache_phase":"PRIVATE_SESSION", "sql":SQL})
    assert attrs == {}
    assert safe_attributes({"cache_reason":"redis_error", "cache_phase":"post_sql"}) == {"cache_reason":"redis_error", "cache_phase":"post_sql"}


def test_output_alias_rename_with_same_binding_is_equivalent():
    renamed = SQL.replace("AS dec", "AS dec_horas_total").replace("ORDER BY dec DESC", "ORDER BY dec_horas_total DESC")
    assert plan(renamed) == plan()
    assert plan(SQL.replace("AS dec", "AS dec_horas_total")) != plan()


@pytest.mark.parametrize("left,right", [
    ("SELECT a AS x, b AS y FROM t ORDER BY x", "SELECT a AS y, b AS x FROM t ORDER BY x"),
    ("SELECT a AS x, b AS x FROM t ORDER BY x", "SELECT a AS y, b AS y FROM t ORDER BY y"),
    ("SELECT SUM(a) AS x FROM t GROUP BY x ORDER BY x", "SELECT SUM(a) AS y FROM t GROUP BY y ORDER BY y"),
    ("SELECT a AS x FROM t WHERE x > 2 ORDER BY x", "SELECT a AS y FROM t WHERE y > 2 ORDER BY y"),
    ("SELECT a AS x FROM t ORDER BY (SELECT x FROM t)", "SELECT a AS y FROM t ORDER BY (SELECT y FROM t)"),
])
def test_changed_binding_or_ambiguous_aliases_do_not_merge(left, right):
    assert canonical_cache_sql(left) != canonical_cache_sql(right)


def test_nested_unordered_limit_is_not_cached():
    assert canonical_cache_sql("SELECT COUNT(*) FROM (SELECT municipio FROM dim_uc LIMIT 3)") is None


def test_aggregate_alias_matching_input_name_has_same_binding():
    import sqlite3
    left = "SELECT alimentador, SUM(dec_horas) AS dec FROM t GROUP BY alimentador ORDER BY dec DESC LIMIT 10"
    right = left.replace("AS dec", "AS dec_horas").replace("ORDER BY dec DESC", "ORDER BY dec_horas DESC")
    assert canonical_cache_sql(left) == canonical_cache_sql(right)
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE t(alimentador TEXT, dec_horas REAL)")
        connection.executemany("INSERT INTO t VALUES (?, ?)", [("A", 1), ("A", 2), ("B", 5)])
        assert connection.execute(left).fetchall() == connection.execute(right).fetchall()
        assert connection.execute(canonical_cache_sql(left)).fetchall() == connection.execute(left).fetchall()
