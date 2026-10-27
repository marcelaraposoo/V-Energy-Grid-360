import pytest

from app.repositories.mock_repo import MockRepository
from app.services import unidades
from app.services.unidades import visao_360


@pytest.fixture
def serie():
    return [
        {"competencia": competencia, "consumo_kwh": 100}
        for competencia in (
            "2024-12", "2025-01", "2025-02",
            "2025-12", "2026-01", "2026-02",
        )
    ]


@pytest.fixture
def repo(serie, monkeypatch):
    repo = MockRepository()
    original = repo.faturas_uc("UC000001")[0]
    faturas = [{**original, "competencia": s["competencia"], "valor_total": 100} for s in serie]
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)
    monkeypatch.setattr(repo, "faturas_uc", lambda uc_id: faturas)
    return repo


@pytest.fixture
def faturas(repo):
    return repo.faturas_uc("UC000001")


@pytest.mark.parametrize(("consumo_atual", "variacao", "classificacao"), [
    (0, -100.0, "reducao"),
    (80, -20.0, "reducao"),
    (100, 0.0, "pequena"),
    (105, 5.0, "pequena"),
    (105.001, 5.001, "moderada"),
    (115, 15.0, "moderada"),
    (115.001, 15.001, "significativa"),
    (120, 20.0, "significativa"),
])
@pytest.mark.parametrize("invertida", [False, True])
def test_conta_alta_classifica_variacao_mensal(
    repo, serie, consumo_atual, variacao, classificacao, invertida,
):
    serie[-1]["consumo_kwh"] = consumo_atual
    if invertida:
        serie.reverse()

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.variacao_pct == pytest.approx(variacao)
    assert diagnostico.consumo.classificacao == classificacao


def test_padrao_usa_os_dois_ultimos_meses_da_uc_e_nao_da_base(repo):
    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert repo.competencias()[-1] == "2026-06"
    assert diagnostico.competencia_atual == "2026-02"
    assert diagnostico.competencia_referencia == "2026-01"
    assert diagnostico.competencias_disponiveis == [
        "2024-12", "2025-01", "2025-02", "2025-12", "2026-01", "2026-02",
    ]


def test_padrao_usa_mes_anterior_disponivel_quando_ha_lacunas(repo, serie, faturas):
    serie.pop(-2)
    faturas.pop(-2)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.competencia_atual == "2026-02"
    assert diagnostico.competencia_referencia == "2025-12"
    assert "2026-01" not in diagnostico.competencias_disponiveis
    assert diagnostico.consumo.variacao_pct == 0


@pytest.mark.parametrize(("atual", "referencia", "valor_atual", "valor_referencia"), [
    ("2026-02", "2026-01", 140, 130),
    ("2026-02", "2025-02", 140, 110),
    ("2025-01", "2024-12", 100, 90),
])
def test_selecao_livre_preserva_historico_e_faturas(
    repo, serie, faturas, atual, referencia, valor_atual, valor_referencia,
):
    for i, (ponto, fatura) in enumerate(zip(serie, faturas, strict=True)):
        ponto["consumo_kwh"] = 90 + i * 10
        fatura["valor_total"] = ponto["consumo_kwh"] * 2
    padrao = visao_360(repo, "UC000001")

    resposta = visao_360(repo, "UC000001", atual, referencia)
    diagnostico = resposta.diagnostico_conta_alta

    assert diagnostico.competencia_atual == atual
    assert diagnostico.competencia_referencia == referencia
    assert diagnostico.consumo.valor_atual == valor_atual
    assert diagnostico.consumo.valor_referencia == valor_referencia
    assert diagnostico.consumo.variacao_pct == pytest.approx((valor_atual / valor_referencia - 1) * 100)
    assert diagnostico.faturamento.valor_atual == valor_atual * 2
    assert diagnostico.faturamento.valor_referencia == valor_referencia * 2
    assert diagnostico.faturamento.variacao_pct == diagnostico.consumo.variacao_pct
    assert resposta.model_dump(exclude={"diagnostico_conta_alta"}) == padrao.model_dump(exclude={"diagnostico_conta_alta"})


def test_permite_selecionar_mes_anterior_aos_ultimos_12_registros():
    resposta = visao_360(MockRepository(), "UC000001", "2023-06", "2022-07")
    diagnostico = resposta.diagnostico_conta_alta

    assert "2022-07" in diagnostico.competencias_disponiveis
    assert "2022-07" not in [c.competencia for c in resposta.consumo]
    assert diagnostico.consumo.variacao_pct is not None
    assert diagnostico.faturamento.variacao_pct is not None


@pytest.mark.parametrize(("atual", "referencia"), [("2020-01", None), (None, "2020-01")])
def test_rejeita_competencia_sem_historico_da_uc(repo, atual, referencia):
    with pytest.raises(ValueError, match="sem histórico para esta UC"):
        visao_360(repo, "UC000001", atual, referencia)


@pytest.mark.parametrize(("atual", "referencia"), [
    ("2025-01", "2026-02"), ("2026-02", "2026-02"), (None, "2026-02"),
])
def test_referencia_deve_ser_anterior_ao_mes_analisado(repo, atual, referencia):
    with pytest.raises(ValueError, match="referência deve ser anterior"):
        visao_360(repo, "UC000001", atual, referencia)


def test_primeiro_mes_do_historico_nao_tem_referencia(repo):
    diagnostico = visao_360(repo, "UC000001", "2024-12").diagnostico_conta_alta

    assert diagnostico.competencia_atual == "2024-12"
    assert diagnostico.competencia_referencia is None
    assert diagnostico.consumo.variacao_pct is None
    assert "não há competência anterior" in diagnostico.consumo.mensagem


@pytest.mark.parametrize(("kwh", "valor", "classe_consumo", "classe_fatura", "contexto"), [
    (103, 130, "pequena", "significativa", "proporcionalmente mais"),
    (125, 110, "significativa", "moderada", "proporcionalmente menos"),
    (120, 120, "significativa", "significativa", "na mesma proporção"),
    (90, 125, "reducao", "significativa", "não foi acompanhado"),
    (125, 90, "significativa", "reducao", "Não houve aumento"),
    (100, 100, "pequena", "pequena", "Não houve aumento"),
])
def test_consumo_e_faturamento_sao_independentes(
    repo, serie, faturas, kwh, valor, classe_consumo, classe_fatura, contexto,
):
    serie[-1]["consumo_kwh"] = kwh
    faturas[-1]["valor_total"] = valor

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao == classe_consumo
    assert diagnostico.faturamento.classificacao == classe_fatura
    assert contexto in diagnostico.mensagem
    if kwh < 100:
        assert "redução" in diagnostico.consumo.mensagem
        assert "aumento" not in diagnostico.consumo.mensagem
    if valor < 100:
        assert "redução" in diagnostico.faturamento.mensagem
        assert "aumento" not in diagnostico.faturamento.mensagem


@pytest.mark.parametrize("indice_ausente", [-1, -2])
def test_fatura_incompleta_nao_impede_analise_de_consumo(repo, faturas, indice_ausente):
    faturas[indice_ausente]["valor_total"] = None

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.variacao_pct == 0
    assert diagnostico.faturamento.variacao_pct is None
    assert diagnostico.faturamento.classificacao is None
    assert faturas[indice_ausente]["competencia"] in diagnostico.faturamento.mensagem


def test_consumo_incompleto_nao_impede_analise_de_faturamento(repo, serie):
    serie.pop()

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.competencia_atual == "2026-02"
    assert diagnostico.consumo.variacao_pct is None
    assert diagnostico.faturamento.variacao_pct == 0


@pytest.mark.parametrize("metrica", ["consumo", "faturamento"])
def test_referencia_zero_nao_calcula_percentual_invalido(repo, serie, faturas, metrica):
    if metrica == "consumo":
        serie[-2]["consumo_kwh"] = 0
    else:
        faturas[-2]["valor_total"] = 0

    resultado = getattr(visao_360(repo, "UC000001").diagnostico_conta_alta, metrica)

    assert resultado.valor_atual == 100
    assert resultado.valor_referencia == 0
    assert resultado.variacao_pct is None
    assert resultado.classificacao is None
    assert "referência igual a zero" in resultado.mensagem


def test_faturas_sem_valor_total_informam_faturamento_indisponivel(repo, faturas):
    for fatura in faturas:
        fatura["valor_total"] = None
    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.faturamento.valor_atual is None
    assert diagnostico.faturamento.valor_referencia is None
    assert diagnostico.faturamento.variacao_pct is None
    assert "dados indisponíveis" in diagnostico.faturamento.mensagem


@pytest.mark.parametrize("quantidade", [0, 1])
def test_historico_insuficiente(repo, serie, faturas, quantidade):
    del serie[quantidade:]
    del faturas[quantidade:]

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.competencia_atual == ("2024-12" if quantidade else None)
    assert diagnostico.competencia_referencia is None
    assert len(diagnostico.competencias_disponiveis) == quantidade
    for metrica in (diagnostico.consumo, diagnostico.faturamento):
        assert metrica.variacao_pct is None
        assert metrica.classificacao is None
        assert metrica.valor_referencia is None
        if quantidade:
            assert metrica.valor_atual == 100
            assert "não há competência anterior" in metrica.mensagem
        else:
            assert metrica.valor_atual is None
            assert "não há competências" in metrica.mensagem


@pytest.mark.parametrize(("kwh", "classificacao"), [(107, "pequena"), (120, "moderada")])
def test_limites_configuraveis(repo, serie, monkeypatch, kwh, classificacao):
    monkeypatch.setattr(unidades, "LIMITE_VARIACAO_PEQUENA_PCT", 10)
    monkeypatch.setattr(unidades, "LIMITE_VARIACAO_MODERADA_PCT", 20)
    serie[-1]["consumo_kwh"] = kwh

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao == classificacao
