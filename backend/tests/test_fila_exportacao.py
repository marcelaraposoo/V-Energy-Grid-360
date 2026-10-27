"""Formatação do CSV da fila de suspeitas (sem depender da API)."""
import csv
import io
from types import SimpleNamespace

from app.services.exportacao import BOM, CABECALHO, fila_para_csv


def _item(**kw):
    base = dict(posicao=1, uc_id="UC00001", titular="Maria da Silva", municipio="Recife", bairro="Boa Viagem",
                classe="B1 Residencial", motivos=["queda de consumo", "leitura zerada"], probabilidade=0.8234,
                energia_recuperavel_kwh_mes=1234.56, prioridade_score=1016.5)
    base.update(kw)
    return SimpleNamespace(**base)


def _ler(texto):
    return list(csv.reader(io.StringIO(texto.removeprefix(BOM), newline=""), delimiter=";"))


def test_comeca_com_bom_e_cabecalho_em_portugues():
    texto = fila_para_csv([])
    assert texto.startswith(BOM)
    assert _ler(texto) == [CABECALHO]


def test_linhas_usam_ponto_e_virgula_virgula_decimal_e_crlf():
    texto = fila_para_csv([_item()])
    assert texto.endswith("\r\n") and "\n" not in texto.replace("\r\n", "")
    [_, linha] = _ler(texto)
    assert linha == ["1", "UC00001", "Maria da Silva", "Recife", "Boa Viagem", "B1 Residencial",
                     "queda de consumo | leitura zerada", "0,82", "1234,6", "1016,5"]


def test_acentos_e_campos_com_ponto_e_virgula_sobrevivem():
    [_, linha] = _ler(fila_para_csv([_item(titular="João; Conceição", bairro="São José")]))
    assert linha[2] == "João; Conceição" and linha[4] == "São José"


def test_texto_que_parece_formula_e_neutralizado():
    [_, linha] = _ler(fila_para_csv([_item(titular="=HYPERLINK(\"http://x\")", bairro="@soma", motivos=["-2+3"])]))
    assert linha[2].startswith("'=") and linha[4] == "'@soma" and linha[6] == "'-2+3"


def test_numeros_nunca_recebem_apostrofo():
    [_, linha] = _ler(fila_para_csv([_item(energia_recuperavel_kwh_mes=-5.0)]))
    assert linha[8] == "-5,0"
