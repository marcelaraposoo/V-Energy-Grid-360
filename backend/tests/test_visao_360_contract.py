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
    uc = repo.buscar_ucs(None, None, None, 1)[0]
    return visao_360(repo, uc["uc_id"]).model_dump(mode="json")


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

        por_competencia = {f["competencia"]: f for f in repo.faturas_uc(uc_id)}
        for fatura in resposta["faturas"] + resposta["faturas_em_aberto"]:
            original = por_competencia[fatura["competencia"]]
            assert fatura | original == fatura

        por_protocolo = {a["protocolo"]: a for a in repo.atendimentos_uc(uc_id)}
        for atendimento in resposta["atendimentos"]:
            original = dict(por_protocolo[atendimento["protocolo"]])
            original["data"] += "T00:00:00"
            assert atendimento | original == atendimento


def test_mock_preenche_campos_previstos_na_gold(resposta):
    assert resposta["cadastro"]["logradouro"]
    assert resposta["cadastro"]["numero"]
    assert isinstance(resposta["cadastro"]["possui_gd"], bool)
    assert "***" in resposta["cadastro"]["titular"]
    assert resposta["interrupcoes"]["escopo"] == "alimentador"
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
        escopo="uc", recentes=[], ultimos_12_meses=0, dec_horas=None, fec_vezes=None,
    )
    contrato = Visao360.model_validate(resposta)
    assert contrato.model_dump(mode="json") == resposta


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("valor_total", "valor inválido"), ("data_pagamento", "2026-02-30")],
)
def test_contrato_rejeita_dados_invalidos_em_faturas(resposta, campo, valor):
    resposta["faturas"][0][campo] = valor
    with pytest.raises(ValidationError) as erro:
        Visao360.model_validate(resposta)
    assert erro.value.errors()[0]["loc"] == ("faturas", 0, campo)


def test_contrato_nao_expoe_campos_internos_do_repositorio(resposta):
    original = deepcopy(resposta)
    resposta["cadastro"]["_base"] = 123
    resposta["faturas"][0]["campo_interno"] = "não expor"
    assert Visao360.model_validate(resposta).model_dump(mode="json") == original


@pytest.mark.parametrize("causa", ["FALHA DE EQUIPAMENTO", None])
def test_contrato_preserva_horarios_das_interrupcoes(resposta, causa):
    ocorrencia = resposta["interrupcoes"]["recentes"][0]
    ocorrencia.update(
        data="2026-06-10T22:35:12",
        data_fim="2026-06-11T00:00:00",
        causa=causa,
    )

    contrato = Visao360.model_validate(resposta)

    assert contrato.model_dump(mode="json")["interrupcoes"]["recentes"][0] == ocorrencia


@pytest.mark.parametrize("data_abertura", [
    "2026-06-10T00:00:00",
    "2026-06-10T22:35:12",
    "2026-06-10T22:35:12-03:00",
])
def test_contrato_preserva_horario_de_abertura_do_atendimento(repo, resposta, data_abertura):
    atendimento = deepcopy(next(iter(repo.d["atendimentos"].values()))[0])
    atendimento["data"] = data_abertura
    resposta["atendimentos"] = [atendimento]

    contrato = Visao360.model_validate(resposta)

    assert contrato.model_dump(mode="json")["atendimentos"][0]["data"] == data_abertura
