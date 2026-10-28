import pytest

from app.agent.guardrails import output_text_rules as rules


def test_lacks_useful_content():
    assert rules.lacks_useful_content("")
    assert rules.lacks_useful_content("   \n")
    assert rules.lacks_useful_content("...")
    assert not rules.lacks_useful_content("Sim")


def test_length_limit_boundary():
    assert not rules.exceeds_max_length("a" * 3000)
    assert rules.exceeds_max_length("a" * 3001)


@pytest.mark.parametrize(
    "text",
    [
        "Veja https://exemplo.com",
        "Veja http://exemplo.com/pagina",
        "Acesse www.exemplo.com",
    ],
)
def test_detects_urls(text):
    assert rules.contains_url(text)


def test_plain_text_is_not_url():
    assert not rules.contains_url("Recife tem 4.820 unidades.")


@pytest.mark.parametrize(
    "text",
    [
        "SELECT * FROM dim_uc",
        "select municipio from dim_uc",
        "INSERT INTO faturas VALUES (1)",
        "UPDATE faturas SET valor = 1",
        "DELETE FROM faturas",
        "DROP TABLE faturas",
        "Use GROUP BY municipio",
        "ordenado com ORDER BY consumo",
        "JOIN fato ON fato.id = dim.id",
    ],
)
def test_detects_sql(text):
    assert rules.contains_sql(text)


@pytest.mark.parametrize(
    "text",
    [
        "O resultado foi ordenado por consumo.",
        "Os dados foram agrupados por município.",
        "Selecione o período desejado.",
    ],
)
def test_business_language_is_not_sql(text):
    assert not rules.contains_sql(text)


def test_detects_echo_of_executed_sql():
    sql = "WHERE municipio = 'Recife' AND classe = 'B1'"

    assert rules.echoes_executed_sql(
        "Filtrei com where municipio =  'Recife'\nand classe = 'B1'.",
        sql,
    )


def test_short_sql_is_not_treated_as_echo():
    assert not rules.echoes_executed_sql("A resposta é 1.", "SELECT 1")


@pytest.mark.parametrize(
    "text",
    [
        "Traceback (most recent call last):",
        'File "app/agent/x.py", line 10, in run',
        "ValueError: valor inválido",
        "ModelHTTPError ao chamar o serviço",
        "status_code: 503",
        "HTTP 429",
        "sqlite3.OperationalError",
        "no such table: dim_uc",
        "'NoneType' object has no attribute",
        "veja app/agent/sql_generator.py",
    ],
)
def test_detects_technical_errors(text):
    assert rules.contains_technical_error(text)


@pytest.mark.parametrize(
    "text",
    [
        "Houve erro de leitura em 3 medidores.",
        "O serviço ficou indisponível por 2 horas.",
        "Recife concentra a maior parte das interrupções.",
    ],
)
def test_business_text_is_not_technical_error(text):
    assert not rules.contains_technical_error(text)


@pytest.mark.parametrize(
    "text",
    [
        "Resposta gerada pelo Gemini.",
        "Consultei via OpenRouter.",
        "Modelo NVIDIA Nemotron.",
        "Usei o Gemma para isso.",
        "Com PydanticAI.",
    ],
)
def test_detects_provider_and_model_names(text):
    assert rules.mentions_provider_or_model(text)


def test_detects_configured_model_names(monkeypatch):
    monkeypatch.setattr(
        rules,
        "_configured_model_terms",
        lambda: ("modelo-secreto-9",),
    )

    assert rules.mentions_provider_or_model(
        "Resposta do modelo-secreto-9."
    )


def test_ordinary_text_is_not_provider_disclosure():
    assert not rules.mentions_provider_or_model(
        "A região metropolitana tem 14 municípios."
    )


@pytest.mark.parametrize(
    "text",
    [
        "<query_result> dados",
        "</user_question>",
        "Meu system prompt diz que",
        "Conforme o prompt de sistema",
        "Minhas instruções internas são",
        "## Segurança\nregras",
    ],
)
def test_detects_prompt_markers(text):
    assert rules.leaks_prompt(text)


def test_detects_verbatim_prompt_fragment():
    fragments = rules._prompt_fragments()

    assert fragments

    assert rules.leaks_prompt(f"Resposta: {fragments[0]}")


def test_ordinary_answer_does_not_leak_prompt():
    assert not rules.leaks_prompt(
        "Recife conta com 4.820 unidades e Olinda com 1.310."
    )