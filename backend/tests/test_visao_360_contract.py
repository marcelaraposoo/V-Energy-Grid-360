from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.repositories.mock_repo import MockRepository
from app.schemas import Visao360
from app.services.unidades import visao_360


@pytest.fixture(scope="module")
def repo():
    return MockRepository()


@pytest.fixture
def resposta(repo):
    ocorrencia = next(o for o in repo.d["fato_interrupcao"] if o["mes_referencia"] >= "2025-07")
    return visao_360(repo, ocorrencia["id_uc"]).model_dump(mode="json")


def test_contrato_preserva_campos_do_mock_em_todas_as_ucs(repo):
    """A tipagem não deve descartar os campos que o endpoint já devolvia."""
    for uc in repo.d["dim_uc"]:
        uc_id = uc["id_uc"]
        resposta = visao_360(repo, uc_id).model_dump(mode="json")
        assert resposta["cadastro"] | repo.uc(uc_id) == resposta["cadastro"]
        assert resposta["medidor"] == repo.medidor_uc(uc_id)
        assert resposta["geracao_distribuida"] == repo.gd_uc(uc_id)
        if uc["possui_gd"]:
            assert resposta["geracao_distribuida"]["modalidade"] == uc["modalidade_gd"]
            assert "fonte" not in resposta["geracao_distribuida"]
        diagnostico = resposta["diagnostico_conta_alta"]
        assert diagnostico["competencias_disponiveis"] == sorted({s["competencia"] for s in repo.consumo_uc(uc_id)})
        assert diagnostico["competencia_atual"] == "2026-06"
        assert diagnostico["competencia_referencia"] == "2026-05"
        interrupcoes = resposta["interrupcoes"]
        originais = repo.ocorrencias("2025-07", "2026-06", uc_id=uc_id)
        assert interrupcoes["escopo"] == "uc"
        assert interrupcoes["qtd_ocorrencias"] == len(originais)
        assert interrupcoes["historico"] == sorted(originais, key=lambda o: o["data"], reverse=True)

        por_competencia = {f["competencia"]: f for f in repo.faturas_uc(uc_id)}
        for fatura in resposta["faturas"] + resposta["faturas_em_aberto"]:
            original = por_competencia[fatura["competencia"]]
            assert fatura | original == fatura

        por_protocolo = {a["protocolo"]: a for a in repo.atendimentos_uc(uc_id)}
        for atendimento in resposta["atendimentos"]:
            original = dict(por_protocolo[atendimento["protocolo"]])
            assert atendimento | original == atendimento


def test_mock_preenche_campos_previstos_na_gold(resposta):
    assert resposta["cadastro"]["logradouro"]
    assert resposta["cadastro"]["numero"]
    assert isinstance(resposta["cadastro"]["possui_gd"], bool)
    assert "***" in resposta["cadastro"]["titular"]
    assert resposta["interrupcoes"]["escopo"] == "uc"
    for fatura in resposta["faturas"]:
        assert fatura["id_fatura"]
        assert (fatura["data_pagamento"] is not None) == (fatura["status"] == "paga")
        assert fatura["valor_total"] > fatura["valor_energia"] > 0
    for ponto in resposta["consumo"]:
        assert ponto["valor_total"] is not None
        assert ponto["valor_total_ano_anterior"] is not None
        assert ponto["variacao_consumo_ano_anterior_pct"] is not None


def test_contrato_aceita_historico_insuficiente_e_blocos_sem_registros(resposta):
    resposta.update(
        consumo=[],
        faturas=[],
        faturas_em_aberto=[],
        medidor=None,
        geracao_distribuida=None,
        atendimentos=[],
    )
    resposta["diagnostico_conta_alta"].update(
        competencias_disponiveis=[], competencia_atual=None, competencia_referencia=None,
    )
    for metrica in ("consumo", "faturamento"):
        resposta["diagnostico_conta_alta"][metrica] = {
            "valor_atual": None,
            "valor_referencia": None,
            "variacao_pct": None,
            "classificacao": None,
            "mensagem": "Dados indisponíveis para comparar.",
        }
    resposta["interrupcoes"].update(
        escopo="uc", historico=[], qtd_ocorrencias=0, duracao_total_min=0, dec_horas=None, fec_vezes=None,
        periodo_inicio=None, periodo_fim=None,
    )
    contrato = Visao360.model_validate(resposta)
    assert contrato.model_dump(mode="json") == resposta


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("valor_total", "valor inválido"), ("data_pagamento", "2026-02-30"),
     ("tributos", "valor inválido"), ("preco_medio_kwh", "valor inválido")],
)
def test_contrato_rejeita_dados_invalidos_em_faturas(resposta, campo, valor):
    resposta["faturas"][0][campo] = valor
    with pytest.raises(ValidationError) as erro:
        Visao360.model_validate(resposta)
    assert erro.value.errors()[0]["loc"] == ("faturas", 0, campo)


@pytest.mark.parametrize("valor", [None, 0.0])
def test_contrato_preserva_tributos_e_preco_medio_nulos_ou_zero(resposta, valor):
    resposta["faturas"][0].update(tributos=valor, preco_medio_kwh=valor)

    fatura = Visao360.model_validate(resposta).model_dump(mode="json")["faturas"][0]

    assert fatura["tributos"] == valor
    assert fatura["preco_medio_kwh"] == valor


def test_contrato_nao_expoe_campos_internos_do_repositorio(resposta):
    original = deepcopy(resposta)
    resposta["cadastro"]["_base"] = 123
    resposta["faturas"][0]["campo_interno"] = "não expor"
    assert Visao360.model_validate(resposta).model_dump(mode="json") == original


@pytest.mark.parametrize("causa", ["FALHA DE EQUIPAMENTO", None])
def test_contrato_preserva_horarios_das_interrupcoes(resposta, causa):
    ocorrencia = resposta["interrupcoes"]["historico"][0]
    ocorrencia.update(
        data="2026-06-10T22:35:12",
        data_fim="2026-06-11T00:00:12",
        duracao_min=85,
        causa=causa,
    )

    contrato = Visao360.model_validate(resposta)

    assert contrato.model_dump(mode="json")["interrupcoes"]["historico"][0] == ocorrencia


@pytest.mark.parametrize(("campo", "valor"), [
    ("uc_id", None), ("data_fim", None), ("duracao_min", -1),
    ("tipo", "TIPO INVALIDO"), ("causa", "CAUSA INVALIDA"),
])
def test_contrato_rejeita_interrupcao_sem_uc_ou_encerramento_e_valores_invalidos(resposta, campo, valor):
    resposta["interrupcoes"]["historico"][0][campo] = valor
    with pytest.raises(ValidationError):
        Visao360.model_validate(resposta)


@pytest.mark.parametrize("campo", ["data", "data_fechamento"])
@pytest.mark.parametrize("data_hora", [
    "2026-06-10T00:00:00",
    "2026-06-10T22:35:12",
    "2026-06-10T22:35:12-03:00",
])
def test_contrato_preserva_horarios_do_atendimento(repo, resposta, campo, data_hora):
    uc_id = repo.d["fato_atendimento"][0]["id_uc"]
    atendimento = deepcopy(repo.atendimentos_uc(uc_id)[0])
    atendimento[campo] = data_hora
    resposta["atendimentos"] = [atendimento]

    contrato = Visao360.model_validate(resposta)

    assert contrato.model_dump(mode="json")["atendimentos"][0][campo] == data_hora
