import sqlite3
from datetime import datetime

import pytest

from app.agent import sql_executor
from app.agent.schemas import (
    SQLExecutionErrorType,
    SQLExecutionStatus,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "pasta com espaço" / "teste.db"
    path.parent.mkdir()

    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE municipios (
            nome TEXT,
            ucs INTEGER,
            receita REAL,
            observacao TEXT
        );
        INSERT INTO municipios VALUES
            ('Recife', 4820, 1000.5, NULL),
            ('Olinda', 1310, 800.0, 'ok'),
            ('Jaboatão dos Guararapes', 900, 650.25, NULL);

        CREATE TABLE numeros (n INTEGER);
        """
    )
    connection.executemany(
        "INSERT INTO numeros VALUES (?)",
        [(i,) for i in range(1, 51)],
    )
    connection.commit()
    connection.close()

    return str(path)


def _execute(sql, db_path, **kwargs):
    return sql_executor.execute_sql(
        sql, database_path=db_path, **kwargs
    )


# ---------------------------------------------------------------
# Execução e formato do resultado
# ---------------------------------------------------------------

def test_executes_select_and_returns_columns_and_rows(db_path):
    outcome = _execute(
        "SELECT nome, ucs FROM municipios ORDER BY ucs DESC", db_path
    )

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert outcome.result.columns == ["nome", "ucs"]
    assert outcome.result.rows == [
        ["Recife", 4820],
        ["Olinda", 1310],
        ["Jaboatão dos Guararapes", 900],
    ]
    assert outcome.result.row_count == 3
    assert outcome.result.truncated is False
    assert outcome.error_type is None


def test_database_path_with_spaces_works(db_path):
    assert " " in db_path

    outcome = _execute("SELECT COUNT(*) FROM municipios", db_path)

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert outcome.result.rows == [[3]]


def test_null_values_are_preserved(db_path):
    outcome = _execute(
        "SELECT nome, observacao FROM municipios WHERE nome = 'Recife'",
        db_path,
    )

    assert outcome.result.rows == [["Recife", None]]


def test_empty_result_has_columns_and_no_rows(db_path):
    outcome = _execute(
        "SELECT nome FROM municipios WHERE ucs > 999999", db_path
    )

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert outcome.result.columns == ["nome"]
    assert outcome.result.rows == []
    assert outcome.result.row_count == 0
    assert outcome.result.truncated is False


def test_aggregate_without_alias_has_a_column_name(db_path):
    outcome = _execute("SELECT SUM(ucs) FROM municipios", db_path)

    assert len(outcome.result.columns) == 1
    assert outcome.result.rows == [[7030]]


# ---------------------------------------------------------------
# Limite de linhas
# ---------------------------------------------------------------

def test_result_above_limit_is_truncated(db_path):
    outcome = _execute(
        "SELECT n FROM numeros ORDER BY n", db_path, max_rows=10
    )

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert len(outcome.result.rows) == 10
    assert outcome.result.row_count == 10
    assert outcome.result.truncated is True
    assert outcome.result.rows[0] == [1]
    assert outcome.result.rows[-1] == [10]


def test_result_exactly_at_limit_is_not_truncated(db_path):
    outcome = _execute(
        "SELECT n FROM numeros ORDER BY n", db_path, max_rows=50
    )

    assert len(outcome.result.rows) == 50
    assert outcome.result.truncated is False


def test_result_below_limit_is_not_truncated(db_path):
    outcome = _execute(
        "SELECT n FROM numeros ORDER BY n", db_path, max_rows=51
    )

    assert len(outcome.result.rows) == 50
    assert outcome.result.truncated is False


# ---------------------------------------------------------------
# Segurança: o banco recusa escrita
# ---------------------------------------------------------------

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM municipios",
        "UPDATE municipios SET ucs = 0",
        "INSERT INTO municipios VALUES ('X', 1, 1.0, NULL)",
        "DROP TABLE municipios",
        "CREATE TABLE novo (a INTEGER)",
        "ALTER TABLE municipios ADD COLUMN extra TEXT",
    ],
)
def test_database_refuses_writes_even_if_the_guardrail_missed(
    db_path, sql
):
    outcome = _execute(sql, db_path)

    assert outcome.status == SQLExecutionStatus.FAILED
    assert outcome.result is None

    # O dado continua intacto.
    check = _execute("SELECT COUNT(*) FROM municipios", db_path)

    assert check.result.rows == [[3]]


def test_attach_cannot_reach_another_database(db_path, tmp_path):
    other = tmp_path / "outro.db"
    sqlite3.connect(other).close()

    outcome = _execute(
        f"ATTACH DATABASE '{other.as_posix()}' AS outro", db_path
    )

    assert outcome.status == SQLExecutionStatus.FAILED


# ---------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------

def test_slow_query_is_interrupted_by_timeout(db_path):
    slow_sql = (
        "WITH RECURSIVE c(x) AS ("
        "SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 500000000"
        ") SELECT COUNT(*) FROM c"
    )

    outcome = _execute(slow_sql, db_path, timeout_seconds=0.3)

    assert outcome.status == SQLExecutionStatus.FAILED
    assert outcome.error_type == SQLExecutionErrorType.TIMEOUT
    assert outcome.elapsed_ms < 5000


# ---------------------------------------------------------------
# Erros
# ---------------------------------------------------------------

def test_unknown_table_is_classified(db_path):
    outcome = _execute("SELECT * FROM nao_existe", db_path)

    assert outcome.status == SQLExecutionStatus.FAILED
    assert outcome.error_type == SQLExecutionErrorType.TABLE_NOT_FOUND


def test_unknown_column_is_classified(db_path):
    outcome = _execute("SELECT coluna_fantasma FROM municipios", db_path)

    assert outcome.error_type == SQLExecutionErrorType.COLUMN_NOT_FOUND


def test_syntax_error_is_an_execution_error(db_path):
    outcome = _execute("SELECT FROM WHERE", db_path)

    assert outcome.error_type == SQLExecutionErrorType.EXECUTION_ERROR


def test_missing_database_file_is_unavailable(tmp_path):
    outcome = _execute(
        "SELECT 1", str(tmp_path / "nao_existe.db")
    )

    assert outcome.status == SQLExecutionStatus.FAILED
    assert (
        outcome.error_type
        == SQLExecutionErrorType.DATABASE_UNAVAILABLE
    )


def test_error_detail_is_kept_for_logs_and_truncated(db_path):
    outcome = _execute("SELECT * FROM nao_existe", db_path)

    assert outcome.error_detail
    assert len(outcome.error_detail) <= 300


def test_error_messages_do_not_reach_the_log_with_row_values(
    db_path, caplog
):
    with caplog.at_level("WARNING"):
        _execute("SELECT * FROM nao_existe", db_path)

    assert "Recife" not in caplog.text


# ---------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (7, 7),
        (1.5, 1.5),
        ("texto", "texto"),
        (True, True),
        (b"abc", "<binário>"),
    ],
)
def test_normalize_basic_values(value, expected):
    assert sql_executor._normalize_value(value) == expected


def test_normalize_decimal_and_dates():
    from decimal import Decimal

    assert sql_executor._normalize_value(Decimal("1.50")) == 1.5
    assert (
        sql_executor._normalize_value(datetime(2026, 6, 1, 10, 30))
        == "2026-06-01T10:30:00"
    )


def test_read_only_uri_encodes_spaces():
    uri = sql_executor.build_read_only_uri("pasta com espaço/x.db")

    assert uri.startswith("file:")
    assert " " not in uri
    assert uri.endswith("?mode=ro")


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA table_info(municipios)",
        "PRAGMA writable_schema = ON",
        "VACUUM",
        "ATTACH DATABASE 'data/portal.db' AS outro",
    ],
)
def test_authorizer_denies_pragma_and_maintenance(db_path, sql):
    outcome = _execute(sql, db_path)

    assert outcome.status == SQLExecutionStatus.FAILED


def test_authorizer_does_not_block_normal_reads(db_path):
    outcome = _execute(
        "SELECT nome, SUM(ucs) AS total FROM municipios "
        "GROUP BY nome HAVING total > 0 ORDER BY total DESC",
        db_path,
    )

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert len(outcome.result.rows) == 3


def test_authorizer_allows_joins_subqueries_and_functions(db_path):
    outcome = _execute(
        "SELECT a.nome, ROUND(a.receita, 1), "
        "(SELECT COUNT(*) FROM numeros) "
        "FROM municipios a JOIN municipios b ON a.nome = b.nome "
        "ORDER BY a.nome",
        db_path,
    )

    assert outcome.status == SQLExecutionStatus.SUCCESS
    assert len(outcome.result.rows) == 3


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM sqlite_master",
        "SELECT * FROM sqlite_stat1",
        "SELECT * FROM sqlite_schema",
    ],
)
def test_internal_sqlite_tables_cannot_be_read(db_path, sql):
    outcome = _execute(sql, db_path)

    assert outcome.status == SQLExecutionStatus.FAILED


def test_normal_tables_are_still_readable_after_the_internal_block(db_path):
    outcome = _execute("SELECT COUNT(*) FROM municipios", db_path)

    assert outcome.status == SQLExecutionStatus.SUCCESS

def test_default_sql_deadline_interrupts_scan_without_poisoning_next_query(db_path, monkeypatch, caplog):
    # Relógio controlado: estoura 10 s no primeiro callback da VM, sem esperar.
    ticks = iter([0., 0.])
    monkeypatch.setattr(sql_executor, "perf_counter", lambda: next(ticks, 11.))
    outcome = _execute(
        "SELECT SUM(a.n * b.n * c.n) FROM numeros a CROSS JOIN numeros b CROSS JOIN numeros c",
        db_path,
    )
    assert sql_executor.DEFAULT_TIMEOUT_SECONDS == 10.
    assert outcome.status == SQLExecutionStatus.FAILED
    assert outcome.error_type == SQLExecutionErrorType.TIMEOUT
    assert outcome.result is None
    assert "SELECT" not in caplog.text
    monkeypatch.undo()
    following = _execute("SELECT SUM(n) AS total FROM numeros", db_path)
    assert following.status == SQLExecutionStatus.SUCCESS
    assert following.result.rows == [[1275]]


def test_monthly_aggregate_preserves_detail_totals_in_synthetic_fixture(tmp_path):
    path = tmp_path / "synthetic.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE fato_consumo_faturamento (mes_referencia TEXT, valor_total REAL);
            INSERT INTO fato_consumo_faturamento VALUES ('2026-01', 2), ('2026-01', 3), ('2026-02', 4);
            CREATE TABLE kpis_mensal AS SELECT mes_referencia, SUM(valor_total) AS receita_total
            FROM fato_consumo_faturamento GROUP BY mes_referencia;
        """)
    detail = _execute(
        "SELECT mes_referencia, SUM(valor_total) FROM fato_consumo_faturamento GROUP BY mes_referencia ORDER BY 2 DESC LIMIT 3",
        str(path),
    )
    aggregate = _execute(
        "SELECT mes_referencia, SUM(receita_total) FROM kpis_mensal GROUP BY mes_referencia ORDER BY 2 DESC LIMIT 3",
        str(path),
    )
    assert detail.status == aggregate.status == SQLExecutionStatus.SUCCESS
    assert detail.result.rows == aggregate.result.rows
