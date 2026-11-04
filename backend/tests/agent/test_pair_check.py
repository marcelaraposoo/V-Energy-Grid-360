import sqlite3

import pytest

from app.agent import pair_check


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "g.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE dim_uc (municipio TEXT, bairro TEXT)")
    c.executemany("INSERT INTO dim_uc VALUES (?,?)", [
        ("Jaboatão dos Guararapes", "Prazeres"),
        ("Olinda", "Centro"), ("Recife", "Centro"),
        ("Abreu e Lima", "Caetés I"), ("Abreu e Lima", "Caetés II"),
    ])
    c.commit(); c.close()
    return str(p)


def test_extract_pair_simple():
    sql = "SELECT COUNT(*) FROM x WHERE municipio = 'Olinda' AND bairro = 'Prazeres'"
    assert pair_check.extract_pair(sql) == ("Olinda", "Prazeres")


@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM x WHERE bairro = 'Centro'",
    "SELECT 1 FROM x WHERE municipio = 'Olinda'",
    "SELECT 1 FROM x WHERE bairro LIKE 'Caet%' AND municipio = 'Olinda'",
    "isso não é sql )))",
    "SELECT 1 FROM x",
])
def test_extract_pair_requires_both_equalities(sql):
    assert pair_check.extract_pair(sql) is None


def test_existing_pair(db):
    assert pair_check.lookup_pair("Olinda", "Centro", db) == ("exists", None)


def test_pair_in_other_municipality(db):
    status, others = pair_check.lookup_pair("Olinda", "Prazeres", db)
    assert status == "other" and others == ["Jaboatão dos Guararapes"]


def test_unknown_neighborhood(db):
    assert pair_check.lookup_pair("Olinda", "Inexistente", db) == ("missing", None)


def test_missing_database_returns_none(tmp_path):
    assert pair_check.lookup_pair("A", "B", str(tmp_path / "x.db")) is None


def test_exact_name_does_not_match_siblings(db):
    # Caetés I existe; igualdade não pega II/III por prefixo.
    assert pair_check.lookup_pair("Abreu e Lima", "Caetés I", db) == ("exists", None)
    assert pair_check.lookup_pair("Abreu e Lima", "Caetés", db) == ("missing", None) or \
        pair_check.lookup_pair("Abreu e Lima", "Caetés", db)[0] == "missing"


@pytest.mark.parametrize("cols,rows,expected", [
    (["n"], [], True), (["n"], [[0]], True), (["n"], [[5]], False),
    (["a", "b"], [[0, 0]], False),
])
def test_empty_or_zero(cols, rows, expected):
    assert pair_check.is_empty_or_zero(cols, rows) is expected


def test_message_uses_only_catalog_names_and_no_user_literal():
    msg = pair_check.clarification_message("other", None, ["Jaboatão dos Guararapes"])
    assert "Jaboatão dos Guararapes" in msg
    assert "http" not in msg and "SELECT" not in msg
    generic = pair_check.clarification_message("missing", None, None)
    assert "Confira" in generic


def test_extract_municipality():
    sql = "SELECT 1 FROM x WHERE municipio = 'Caetés' AND mes_referencia >= '2025-07'"
    assert pair_check.extract_municipality(sql) == "Caetés"
    assert pair_check.extract_municipality("SELECT 1 FROM x") is None
    assert pair_check.extract_municipality("isso não é sql )))") is None


def test_municipality_exists(db):
    assert pair_check.municipality_exists("Olinda", db) is True
    assert pair_check.municipality_exists("Caetés", db) is False


def test_municipality_check_without_database(tmp_path):
    assert pair_check.municipality_exists("Olinda", str(tmp_path / "x.db")) is None