import re
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.mock.mock_data import DATA_REFERENCIA
from app.repositories.mock_repo import MockRepository
from app.schemas import AtendimentoUC
from app.services.unidades import visao_360


@pytest.fixture(scope="module")
def repo():
    return MockRepository()


def test_mock_atendimento_segue_b1_da_gold(repo):
    campos = set("""
        protocolo id_uc municipio bairro classe canal assunto subassunto
        data_hora_abertura data_hora_fechamento mes_referencia aberto
        tempo_resolucao_horas qtd_tratativas ultima_acao nota_satisfacao
    """.split())
    por_uc = {uc["id_uc"]: uc for uc in repo.d["dim_uc"]}
    fatos = repo.d["fato_atendimento"]
    assert fatos
    assert len({a["protocolo"] for a in fatos}) == len(fatos)
    assert {a["canal"] for a in fatos} == {"TELEFONE", "APP", "WHATSAPP", "SITE", "PRESENCIAL"}
    assert {a["ultima_acao"] for a in fatos} == {
        "ABERTURA", "ANALISE", "DESPACHO", "RETORNO AO CLIENTE", "ENCERRAMENTO",
    }
    # A B1 confirma estes três pares; os outros dependem do dicionário da Silver.
    assert {(a["assunto"], a["subassunto"]) for a in fatos} == {
        ("DANO ELETRICO", "VISTORIA"), ("GERACAO DISTRIBUIDA", "VISTORIA"),
        ("LIGACAO NOVA", "VISTORIA"),
    }
    assert any(a["nota_satisfacao"] is None for a in fatos)
    for a in fatos:
        assert set(a) == campos
        assert re.fullmatch(r"AT\d{9}", a["protocolo"])
        uc = por_uc[a["id_uc"]]
        for campo in ("municipio", "bairro", "classe"):
            assert a[campo] == uc[campo]
        abertura = datetime.fromisoformat(a["data_hora_abertura"])
        fechamento = datetime.fromisoformat(a["data_hora_fechamento"])
        assert "T" in a["data_hora_abertura"] and "T" in a["data_hora_fechamento"]
        assert abertura < fechamento
        assert fechamento.date() <= DATA_REFERENCIA
        assert a["mes_referencia"] == abertura.strftime("%Y-%m")
        assert a["aberto"] is False
        assert a["tempo_resolucao_horas"] == round((fechamento - abertura).total_seconds() / 3600, 2)
        assert 1 <= a["tempo_resolucao_horas"] <= 719
        assert 1 <= a["qtd_tratativas"] <= 3
        if a["nota_satisfacao"] is not None:
            nota = Decimal(str(a["nota_satisfacao"]))
            assert Decimal("1.3") <= nota <= 5
            assert nota * 10 == (nota * 10).to_integral_value()


def test_visao_360_filtra_uc_preserva_campos_e_ordena_por_abertura(repo):
    uc_id = repo.d["fato_atendimento"][0]["id_uc"]
    fatos = sorted(
        [a for a in repo.d["fato_atendimento"] if a["id_uc"] == uc_id],
        key=lambda a: a["data_hora_abertura"], reverse=True,
    )
    resposta = visao_360(repo, uc_id.lower()).model_dump(mode="json")["atendimentos"]

    assert len(resposta) == len(fatos)
    for a, fato in zip(resposta, fatos, strict=True):
        assert a["uc_id"] == fato["id_uc"] == uc_id
        assert a["data"] == fato["data_hora_abertura"]
        assert a["data_fechamento"] == fato["data_hora_fechamento"]
        assert "status" not in a and "tratativas" not in a
        for campo in (
            "protocolo", "canal", "assunto", "subassunto", "aberto",
            "tempo_resolucao_horas", "qtd_tratativas", "ultima_acao", "nota_satisfacao",
        ):
            assert a[campo] == fato[campo]


def test_uc_sem_chamados_nao_herda_atendimentos_de_outras_ucs(repo):
    com_chamados = {a["id_uc"] for a in repo.d["fato_atendimento"]}
    uc_id = next(uc["id_uc"] for uc in repo.d["dim_uc"] if uc["id_uc"] not in com_chamados)
    assert visao_360(repo, uc_id).atendimentos == []


@pytest.mark.parametrize(("aberto", "ultima_acao"), [(False, "ABERTURA"), (True, "ENCERRAMENTO")])
def test_situacao_independe_da_ultima_acao_e_preserva_nulos(repo, aberto, ultima_acao):
    uc_id = repo.d["fato_atendimento"][0]["id_uc"]
    original = repo.atendimentos_uc(uc_id)[0]
    original.update(aberto=aberto, ultima_acao=ultima_acao, nota_satisfacao=None)
    if aberto:
        original.update(data_fechamento=None, tempo_resolucao_horas=None)

    atendimento = AtendimentoUC.model_validate(original).model_dump(mode="json")

    assert atendimento == original


@pytest.mark.parametrize(("campo", "valor"), [
    ("protocolo", "AT0000001"), ("canal", "LOJA"), ("assunto", "Conta alta"),
    ("subassunto", "INVALIDO"), ("ultima_acao", "RESOLVIDO"), ("aberto", None),
    ("qtd_tratativas", 0), ("qtd_tratativas", 4), ("tempo_resolucao_horas", -1),
    ("nota_satisfacao", 0), ("nota_satisfacao", 6), ("nota_satisfacao", 3.25),
])
def test_contrato_rejeita_atendimento_fora_dos_dominios_da_gold(repo, campo, valor):
    uc_id = repo.d["fato_atendimento"][0]["id_uc"]
    atendimento = repo.atendimentos_uc(uc_id)[0]
    atendimento[campo] = valor
    with pytest.raises(ValidationError):
        AtendimentoUC.model_validate(atendimento)
