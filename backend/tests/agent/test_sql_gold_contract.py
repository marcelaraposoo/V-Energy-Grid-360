"""Regressões C4.1 sem LLM: contrato estático, dados artificiais e Gold local RO."""

import json
import re
import sqlite3
import time
from pathlib import Path

import pytest

from app.agent.context.loader import CONTEXT_PATH
from app.agent.prompts.sql_generation.loader import load_sql_generation_prompts
from app.agent.sql_generator import build_sql_generation_prompt
from benchmarks import build_synthetic_db as benchmark


BACKEND = Path(__file__).resolve().parents[2]
GOLD_PATH = BACKEND.parent / "data/gold/gold.db"
CONTRACT_PATH = BACKEND / "tests/fixtures/gold_agent_contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tables"]

# Cada SELECT tem uma forma de resultado explícita. Nenhum valor do case é fixado.
SQL_CASES = {
    "consumo_mensal": (
        "SELECT mes_referencia,consumo_total_kwh FROM kpis_mensal "
        "WHERE mes_referencia BETWEEN '2026-05' AND '2026-06' ORDER BY mes_referencia",
        ["mes_referencia", "consumo_total_kwh"],
    ),
    "consumo_municipio": (
        "SELECT municipio,SUM(consumo_kwh) AS consumo_kwh FROM fato_consumo_faturamento "
        "WHERE mes_referencia='2026-06' GROUP BY municipio",
        ["municipio", "consumo_kwh"],
    ),
    "faturamento": (
        "SELECT mes_referencia,SUM(valor_total) AS faturamento_com_tributos "
        "FROM fato_consumo_faturamento WHERE mes_referencia BETWEEN '2026-05' AND '2026-06' "
        "GROUP BY mes_referencia ORDER BY mes_referencia",
        ["mes_referencia", "faturamento_com_tributos"],
    ),
    "receita": (
        "SELECT SUM(receita_0) AS receita_0,SUM(receita_1) AS receita_1,"
        "(SUM(volume_kwh_1)-SUM(volume_kwh_0))*SUM(receita_0)/NULLIF(SUM(volume_kwh_0),0) AS efeito_volume,"
        "(SUM(receita_1)/NULLIF(SUM(volume_kwh_1),0)-SUM(receita_0)/NULLIF(SUM(volume_kwh_0),0))"
        "*SUM(volume_kwh_1) AS efeito_preco FROM receita_decomposicao",
        ["receita_0", "receita_1", "efeito_volume", "efeito_preco"],
    ),
    "inadimplencia": (
        "SELECT municipio,100.0*SUM(CASE WHEN em_aberto=1 THEN valor_total ELSE 0 END)"
        "/NULLIF(SUM(valor_total),0) AS inadimplencia_pct FROM fato_consumo_faturamento "
        "WHERE mes_referencia='2026-06' GROUP BY municipio",
        ["municipio", "inadimplencia_pct"],
    ),
    "ranking": (
        "SELECT municipio,SUM(receita_1)-SUM(receita_0) AS variacao_receita "
        "FROM receita_decomposicao GROUP BY municipio ORDER BY variacao_receita DESC LIMIT 5",
        ["municipio", "variacao_receita"],
    ),
    "dec_fec_ponderado": (
        "SELECT municipio,SUM(horas_interrompidas)/NULLIF(SUM(qtd_ucs_alimentador_mes),0) AS dec_horas,"
        "1.0*SUM(qtd_interrupcoes)/NULLIF(SUM(qtd_ucs_alimentador_mes),0) AS fec "
        "FROM dec_fec_alimentador_mensal WHERE mes_referencia='2026-06' GROUP BY municipio",
        ["municipio", "dec_horas", "fec"],
    ),
    "interrupcoes": (
        "SELECT COUNT(DISTINCT id_uc) AS ucs_afetadas,AVG(duracao_min) AS duracao_media_min "
        "FROM fato_interrupcao WHERE data_hora_inicio>='2026-06-01 00:00:00' "
        "AND data_hora_inicio<'2026-07-01 00:00:00'",
        ["ucs_afetadas", "duracao_media_min"],
    ),
    "atendimentos": (
        "SELECT canal,COUNT(*) AS chamados,AVG(tempo_resolucao_horas) AS resolucao_media_horas "
        "FROM fato_atendimento WHERE data_hora_abertura>='2026-06-01 00:00:00' "
        "AND data_hora_abertura<'2026-07-01 00:00:00' GROUP BY canal",
        ["canal", "chamados", "resolucao_media_horas"],
    ),
    "fila": (
        "SELECT prioridade,id_uc,score,motivo,kwh_estimado_recuperar_mes,data_referencia_score "
        "FROM fila_inspecao ORDER BY prioridade LIMIT 5",
        ["prioridade", "id_uc", "score", "motivo", "kwh_estimado_recuperar_mes", "data_referencia_score"],
    ),
    "troca_medidor": (
        "SELECT mes_troca,tipo_medidor_antigo,tipo_medidor_novo,COUNT(*) AS trocas "
        "FROM fato_troca_medidor GROUP BY mes_troca,tipo_medidor_antigo,tipo_medidor_novo "
        "ORDER BY mes_troca",
        ["mes_troca", "tipo_medidor_antigo", "tipo_medidor_novo", "trocas"],
    ),
    "join_sem_fanout": (
        "SELECT SUM(f.consumo_kwh) AS consumo_kwh FROM fato_consumo_faturamento f "
        "JOIN (SELECT DISTINCT id_uc FROM fato_interrupcao WHERE mes_referencia='2026-06') i "
        "ON i.id_uc=f.id_uc WHERE f.mes_referencia='2026-06'",
        ["consumo_kwh"],
    ),
}


def context_tables():
    sections = re.split(r"^# \d+\. `([^`]+)`", CONTEXT_PATH.read_text(encoding="utf-8"), flags=re.M)
    return {
        sections[i]: set(re.findall(r"^- `([^`]+)` —", sections[i + 1], flags=re.M))
        for i in range(1, len(sections), 2)
    }


def assert_physical_contract(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(CONTRACT) <= tables
    for name, table in CONTRACT.items():
        physical = {r[1]: r[2].upper() for r in conn.execute(f'PRAGMA table_info("{name}")')}
        for column, kind in table["columns"].items():
            assert physical.get(column) == kind, f"{name}.{column}: esperado {kind}, encontrado {physical.get(column)}"


def open_local_gold(path):
    if not path.is_file():
        pytest.skip("Gold local ausente: disponibilize data/gold/gold.db para compatibilidade física")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


@pytest.fixture(scope="module")
def real_gold():
    conn = open_local_gold(GOLD_PATH)
    before = GOLD_PATH.stat()
    try:
        yield conn
    finally:
        conn.close()
        after = GOLD_PATH.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def test_missing_gold_skips_without_creating_a_database(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(pytest.skip.Exception, match="Gold local ausente"):
        open_local_gold(path)
    assert not path.exists()


def test_context_matches_static_names_and_grains():
    tables = context_tables()
    assert set(tables) == set(CONTRACT)
    assert "fato_segmento_mensal" in tables
    for name, table in CONTRACT.items():
        assert tables[name] == set(table["columns"]), name
        assert table["grain"] and table["grain_key"]
        assert set(table["grain_key"]) <= tables[name]
    text = CONTEXT_PATH.read_text(encoding="utf-8")
    for old in ("data_inicio", "data_fim", "qtd_ucs_alimentador"):
        assert f"`{old}`" not in text


@pytest.mark.parametrize("required", [
    "cadastro atual", "UC-mês", "1 linha = 1 UC no snapshot", "1 linha = 1 troca",
    "pré-agregue cada lado", "use `EXISTS`", "NÃO é 1:1", "Não some indicadores agregados",
    "SUM(qtd_ucs_alimentador_mes)", "horas/UC", "interrupções/UC", "Não use média simples",
    "recalcule `P0 = R0 / V0`", "P1 = R1 / V1", "NÃO são aditivos",
    "energia sem tributos", "bandeira embutida", "arrecadação/caixa",
    "percentual de faturas", "inadimplência atual",
    "intervalo semiaberto", "< '2026-07-01 00:00:00'", "Competência",
    "não significa perda confirmada", "não é necessariamente probabilidade calibrada",
    "não prova causalidade", "snapshots futuros",
])
def test_generator_receives_semantic_contract(required):
    context = CONTEXT_PATH.read_text(encoding="utf-8")
    prompt = build_sql_generation_prompt("Pergunta sintética", context)
    assert required in prompt


@pytest.mark.parametrize("required", [
    "dialeto SQLite", "Nunca use `SELECT *`", "colunas necessárias",
    "nomes semelhantes", "Respeite o grão", "Não some razões", "aliases legíveis",
])
def test_fixed_prompt_enforces_sql_guidance(required):
    assert required in load_sql_generation_prompts()


@pytest.fixture(scope="module")
def synthetic_gold():
    """Dados pequenos, integralmente artificiais, com armadilhas semânticas deliberadas."""
    conn = sqlite3.connect(":memory:")
    for name, table in CONTRACT.items():
        definition = ",".join(f'"{column}" {kind}' for column, kind in table["columns"].items())
        conn.execute(f'CREATE TABLE "{name}" ({definition})')

    def add(table, **row):
        conn.execute(f'INSERT INTO "{table}" ({",".join(row)}) VALUES ({",".join("?" for _ in row)})', tuple(row.values()))

    for number in (1, 2):
        add("dim_uc", id_uc=f"S{number}", municipio="Sintético", bairro=f"B{number}",
            classe="RESIDENCIAL", alimentador=f"A{number}")
    for uc, consumo, valor, aberto in [("S1", 100, 100, 1), ("S2", 300, 200, 0)]:
        add("fato_consumo_faturamento", id_uc=uc, mes_referencia="2026-06", municipio="Sintético",
            consumo_kwh=consumo, valor_energia=valor, valor_total=valor*1.2, em_aberto=aberto, dias_atraso=10)
    add("fato_consumo_faturamento", id_uc="S1", mes_referencia="2026-05", municipio="Sintético",
        consumo_kwh=80, valor_energia=80, valor_total=96, em_aberto=0)
    for month, value in [("2026-05", 80), ("2026-06", 400)]:
        add("kpis_mensal", mes_referencia=month, consumo_total_kwh=value)
    for bairro, v0, v1, r0, r1 in [("B1", 100, 50, 100, 75), ("B2", 100, 200, 200, 600)]:
        add("receita_decomposicao", municipio="Sintético", bairro=bairro, classe="RESIDENCIAL",
            volume_kwh_0=v0, volume_kwh_1=v1, receita_0=r0, receita_1=r1,
            efeito_volume=(v1-v0)*r0/v0, efeito_preco=(r1/v1-r0/v0)*v1)
    for alimentador, ucs, horas, count in [("A1", 1, 10, 4), ("A2", 9, 18, 9)]:
        add("dec_fec_alimentador_mensal", alimentador=alimentador, municipio="Sintético",
            mes_referencia="2026-06", qtd_ucs_alimentador_mes=ucs, horas_interrompidas=horas,
            qtd_interrupcoes=count, dec_horas=horas/ucs, fec=count/ucs)
    for i, uc, start in [(1, "S1", "2026-06-01 00:00:00"), (2, "S1", "2026-06-30 23:59:00"),
                         (3, "S2", "2026-06-15 10:00:00"), (4, "S2", "2026-07-01 00:00:00")]:
        add("fato_interrupcao", id_ocorrencia=f"I{i}", id_uc=uc, data_hora_inicio=start,
            mes_referencia=start[:7], duracao_min=60)
        add("fato_atendimento", protocolo=f"P{i}", id_uc=uc, canal="APP",
            data_hora_abertura=start, mes_referencia=start[:7], tempo_resolucao_horas=2)
    add("fila_inspecao", id_uc="S1", prioridade=1, score=45, motivo="Sinal artificial",
        kwh_estimado_recuperar_mes=20, data_referencia_score="2026-06-30")
    # Duas trocas na mesma UC: evita cristalizar a unicidade acidental do snapshot real.
    for month, meter in [("2026-03", "M1"), ("2026-06", "M2")]:
        add("fato_troca_medidor", id_uc="S1", mes_troca=month, id_medidor_novo=meter,
            tipo_medidor_antigo="ELETRONICO", tipo_medidor_novo="SMART")
    yield conn
    conn.close()


@pytest.mark.parametrize("case", SQL_CASES)
def test_representative_sql_on_synthetic_gold(synthetic_gold, case):
    sql, columns = SQL_CASES[case]
    cur = synthetic_gold.execute(sql)
    assert [c[0] for c in cur.description] == columns
    assert cur.fetchall(), case


def test_weighted_indicators_and_decomposition(synthetic_gold):
    conn = synthetic_gold
    assert conn.execute(SQL_CASES["dec_fec_ponderado"][0]).fetchone()[1:] == pytest.approx((2.8, 1.3))
    assert conn.execute(SQL_CASES["receita"][0]).fetchone() == pytest.approx((300, 675, 75, 300))
    assert conn.execute("SELECT SUM(efeito_volume) FROM receita_decomposicao").fetchone()[0] != 75
    assert conn.execute(SQL_CASES["inadimplencia"][0]).fetchone()[1] == pytest.approx(100/3)


def test_dates_counts_and_joins_respect_grain(synthetic_gold):
    conn = synthetic_gold
    assert conn.execute(SQL_CASES["interrupcoes"][0]).fetchone() == (2, 60)
    assert conn.execute(SQL_CASES["atendimentos"][0]).fetchone() == ("APP", 3, 2)
    assert conn.execute(SQL_CASES["join_sem_fanout"][0]).fetchone() == (400,)
    assert conn.execute(SQL_CASES["troca_medidor"][0]).fetchall() == [
        ("2026-03", "ELETRONICO", "SMART", 1), ("2026-06", "ELETRONICO", "SMART", 1),
    ]


def test_synthetic_fixture_and_benchmark_schema_follow_static_contract(synthetic_gold):
    assert_physical_contract(synthetic_gold)
    assert {name: dict(cols) for name, cols in benchmark.TABLES.items()} == {
        name: table["columns"] for name, table in CONTRACT.items()
    }
    for table, cols in benchmark.GENERATED_COLUMNS.items():
        assert set(dict(cols)) <= set(CONTRACT[table]["columns"])


def test_benchmark_builds_complete_contract(tmp_path):
    path = tmp_path / "synthetic.db"
    benchmark.main(n_ucs=80, seed=42, output=path)
    conn = sqlite3.connect(path)
    try:
        assert_physical_contract(conn)
        aggregate = conn.execute('SELECT SUM(consumo_kwh),SUM(receita_total) FROM fato_segmento_mensal').fetchone()
        detailed = conn.execute('SELECT SUM(consumo_kwh),SUM(valor_total) FROM fato_consumo_faturamento').fetchone()
        assert aggregate == pytest.approx(detailed)
        for sql, columns in SQL_CASES.values():
            cur = conn.execute(sql)
            assert [c[0] for c in cur.description] == columns
            cur.fetchall()
        assert conn.execute("SELECT COUNT(*) FROM fato_atendimento WHERE length(data_hora_abertura)<>19").fetchone()[0] == 0
    finally:
        conn.close()


def test_real_gold_matches_static_and_context_contract(real_gold):
    assert real_gold.execute("PRAGMA query_only").fetchone()[0] == 1
    assert_physical_contract(real_gold)
    expected = context_tables()
    for name, columns in expected.items():
        actual = {r[1] for r in real_gold.execute(f'PRAGMA table_info("{name}")')}
        assert columns <= actual


@pytest.mark.parametrize("case", SQL_CASES)
def test_representative_sql_on_real_gold_read_only(real_gold, case):
    sql, columns = SQL_CASES[case]
    start = time.monotonic()
    real_gold.set_progress_handler(lambda: int(time.monotonic()-start > 10), 10000)
    try:
        cur = real_gold.execute(sql)
        assert [c[0] for c in cur.description] == columns
        rows = cur.fetchall()
        assert rows, f"Sem estrutura representativa para {case}"
        if case in {"ranking", "fila"}:
            assert len(rows) <= 5
    finally:
        real_gold.set_progress_handler(None, 0)
