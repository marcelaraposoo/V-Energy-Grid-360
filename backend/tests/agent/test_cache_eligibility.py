import pytest
from app.agent.state.cache_eligibility import prove_independence, resolve_intent, independent_lookup_key

QUESTION = "Quais os 3 meses com maiores valores faturados em todo o histórico da distribuidora, sem filtros adicionais?"
SQL = "SELECT mes_referencia, receita_total AS valor_faturado FROM kpis_mensal ORDER BY valor_faturado DESC LIMIT 3"

@pytest.mark.parametrize("sql", [SQL, "SELECT mes_referencia, SUM(receita_total) AS total FROM kpis_mensal GROUP BY mes_referencia ORDER BY total DESC LIMIT 3"])
def test_complete_contract_and_verified_sql_produce_certificate(sql):
    proof = prove_independence(QUESTION, sql)
    assert proof is not None
    assert proof.intent_hash and proof.sql_hash
    assert "SELECT" not in str(proof.metadata())

@pytest.mark.parametrize("question", [
    "Quais os 3 meses com maiores gastos?", "E no mês anterior?",
    "Quais os 3 meses com maiores valores faturados?",
    "Quais os 3 meses com maiores valores faturados em todo o histórico em Recife?",
    "Quais os 3 meses com maiores valores faturados em todo o histórico exceto janeiro?",
    "Não mostre os 3 meses com maiores valores faturados em todo o histórico.",
])
def test_ambiguous_relative_or_incomplete_contract_is_not_certified(question):
    assert resolve_intent(question) is None
    assert prove_independence(question, SQL) is None

@pytest.mark.parametrize("sql", [
    SQL.replace("receita_total", "receita_energia"),
    SQL.replace("LIMIT 3", "LIMIT 2"),
    SQL.replace("DESC", "ASC"),
    SQL.replace("ORDER BY", "WHERE mes_referencia = '2024-01' ORDER BY"),
    SQL.replace("kpis_mensal", "kpis_mensal JOIN dim_uc ON 1=1"),
    SQL + "; SELECT 1", SQL + " -- independently verified by LLM",
    SQL.replace("valor_faturado", "total_olinda"),
])
def test_entire_sql_must_match_question_not_a_model_claim(sql):
    assert prove_independence(QUESTION, sql) is None

@pytest.mark.parametrize("session,version", [("other", "v1"), ("s", "v2")])
def test_pointer_is_bound_to_session_and_snapshot(session, version):
    assert independent_lookup_key(QUESTION, "s", "v1") != independent_lookup_key(QUESTION, session, version)

def test_financial_perspectives_do_not_share_intents():
    revenue = QUESTION.replace("valores faturados", "receitas de energia")
    assert resolve_intent(revenue) != resolve_intent(QUESTION)
    assert prove_independence(revenue, SQL) is None


def test_future_trusted_user_identity_is_part_of_independent_scope():
    assert independent_lookup_key(QUESTION, "s", "v", user_identity="a") != independent_lookup_key(QUESTION, "s", "v", user_identity="b")
