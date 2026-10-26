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
    competencias = [ponto["competencia"] for ponto in serie]
    monkeypatch.setattr(repo, "competencias", lambda: competencias)
    return repo


@pytest.fixture
def faturas(repo, serie, monkeypatch):
    original = repo.faturas_uc("UC000001")[0]
    faturas = [{**original, "competencia": s["competencia"], "valor_total": 100} for s in serie]
    monkeypatch.setattr(repo, "faturas_uc", lambda uc_id: faturas)
    return faturas


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
def test_conta_alta_compara_tres_meses_equivalentes(
    repo, serie, monkeypatch, consumo_atual, variacao, classificacao, invertida,
):
    for ponto in serie[3:]:
        ponto["consumo_kwh"] = consumo_atual
    if invertida:
        serie.reverse()
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.variacao_pct == pytest.approx(variacao)
    assert diagnostico.consumo.classificacao == classificacao


@pytest.mark.parametrize("indices_ausentes", [
    (0, 1),
    (0, 1, 2),
    (3,),
    (4,),
    (0, 1, 2, 3, 4, 5),
])
def test_conta_alta_com_historico_parcial(repo, serie, monkeypatch, indices_ausentes):
    serie = [ponto for i, ponto in enumerate(serie) if i not in indices_ausentes]
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao is None
    assert diagnostico.consumo.variacao_pct is None
    assert "dados indisponíveis" in diagnostico.consumo.mensagem
    assert diagnostico.competencias_atuais == ["2025-12", "2026-01", "2026-02"]


def test_conta_alta_com_consumo_anterior_zero(repo, serie, monkeypatch):
    for ponto in serie[:3]:
        ponto["consumo_kwh"] = 0
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao is None
    assert diagnostico.consumo.variacao_pct is None
    assert diagnostico.consumo.valor_referencia == 0
    assert "referência igual a zero" in diagnostico.consumo.mensagem


def test_conta_alta_exige_meses_consecutivos(repo, serie, monkeypatch):
    serie[1]["competencia"] = "2025-03"
    serie[4]["competencia"] = "2026-03"
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao is None
    assert diagnostico.consumo.variacao_pct is None
    assert "dados indisponíveis" in diagnostico.consumo.mensagem


@pytest.mark.parametrize(("modo", "atuais", "referencia", "valor_atual", "valor_referencia"), [
    ("mes_anterior", ["2026-02"], ["2026-01"], 140, 130),
    ("ano_anterior", ["2026-02"], ["2025-02"], 140, 110),
    ("trimestre_ano_anterior", ["2025-12", "2026-01", "2026-02"],
     ["2024-12", "2025-01", "2025-02"], 390, 300),
])
def test_selecao_do_periodo_preserva_historico(
    repo, serie, faturas, monkeypatch, modo, atuais, referencia, valor_atual, valor_referencia,
):
    for i, (ponto, fatura) in enumerate(zip(serie, faturas, strict=True)):
        ponto["consumo_kwh"] = 90 + i * 10
        fatura["valor_total"] = ponto["consumo_kwh"] * 2
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)
    padrao = visao_360(repo, "UC000001")

    resposta = visao_360(repo, "UC000001", modo)
    diagnostico = resposta.diagnostico_conta_alta

    assert diagnostico.comparacao == modo
    assert diagnostico.competencias_atuais == atuais
    assert diagnostico.competencias_referencia == referencia
    assert diagnostico.consumo.valor_atual == valor_atual
    assert diagnostico.consumo.valor_referencia == valor_referencia
    assert diagnostico.consumo.variacao_pct == pytest.approx((valor_atual / valor_referencia - 1) * 100)
    assert diagnostico.faturamento.valor_atual == valor_atual * 2
    assert diagnostico.faturamento.valor_referencia == valor_referencia * 2
    assert diagnostico.faturamento.variacao_pct == diagnostico.consumo.variacao_pct
    assert resposta.consumo == padrao.consumo
    assert resposta.faturas == padrao.faturas
    assert padrao.diagnostico_conta_alta.comparacao == "trimestre_ano_anterior"


@pytest.mark.parametrize(("kwh", "valor", "classe_consumo", "classe_fatura", "contexto"), [
    (103, 130, "pequena", "significativa", "proporcionalmente mais"),
    (125, 110, "significativa", "moderada", "proporcionalmente menos"),
    (120, 120, "significativa", "significativa", "na mesma proporção"),
    (90, 125, "reducao", "significativa", "não foi acompanhado"),
    (125, 90, "significativa", "reducao", "Não houve aumento"),
    (100, 100, "pequena", "pequena", "Não houve aumento"),
])
def test_consumo_e_faturamento_sao_independentes(
    repo, serie, faturas, monkeypatch, kwh, valor, classe_consumo, classe_fatura, contexto,
):
    for ponto in serie[3:]:
        ponto["consumo_kwh"] = kwh
    for fatura in faturas[3:]:
        fatura["valor_total"] = valor
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

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


@pytest.mark.parametrize("indice_ausente", [0, 3])
def test_fatura_incompleta_nao_impede_analise_de_consumo(repo, serie, faturas, monkeypatch, indice_ausente):
    faturas[indice_ausente]["valor_total"] = None
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.variacao_pct == 0
    assert diagnostico.faturamento.variacao_pct is None
    assert diagnostico.faturamento.classificacao is None
    assert faturas[indice_ausente]["competencia"] in diagnostico.faturamento.mensagem


def test_consumo_incompleto_nao_impede_analise_de_faturamento(repo, serie, faturas, monkeypatch):
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie[:-1])

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.variacao_pct is None
    assert diagnostico.faturamento.variacao_pct == 0


def test_faturamento_com_referencia_zero(repo, serie, faturas, monkeypatch):
    for fatura in faturas[:3]:
        fatura["valor_total"] = 0
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.faturamento.valor_atual == 300
    assert diagnostico.faturamento.valor_referencia == 0
    assert diagnostico.faturamento.variacao_pct is None
    assert diagnostico.faturamento.classificacao is None
    assert "referência igual a zero" in diagnostico.faturamento.mensagem


def test_mock_sem_valor_total_informa_faturamento_indisponivel(repo):
    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.faturamento.valor_atual is None
    assert diagnostico.faturamento.valor_referencia is None
    assert diagnostico.faturamento.variacao_pct is None
    assert "dados indisponíveis" in diagnostico.faturamento.mensagem


def test_competencias_vazias(repo, monkeypatch):
    monkeypatch.setattr(repo, "competencias", lambda: [])

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.competencias_atuais == []
    assert diagnostico.competencias_referencia == []
    assert diagnostico.consumo.variacao_pct is None
    assert diagnostico.faturamento.variacao_pct is None
    assert "não há competências" in diagnostico.mensagem


@pytest.mark.parametrize(("kwh", "classificacao"), [(107, "pequena"), (120, "moderada")])
def test_limites_configuraveis(repo, serie, monkeypatch, kwh, classificacao):
    monkeypatch.setattr(unidades, "LIMITE_VARIACAO_PEQUENA_PCT", 10)
    monkeypatch.setattr(unidades, "LIMITE_VARIACAO_MODERADA_PCT", 20)
    for ponto in serie[3:]:
        ponto["consumo_kwh"] = kwh
    monkeypatch.setattr(repo, "consumo_uc", lambda uc_id: serie)

    diagnostico = visao_360(repo, "UC000001").diagnostico_conta_alta

    assert diagnostico.consumo.classificacao == classificacao
