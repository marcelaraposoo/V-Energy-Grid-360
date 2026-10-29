"""Leitura e validação da planilha de resultados de campo (sem API, só o arquivo)."""
import pytest

from app.services.importacao import PlanilhaInvalida, ler_planilha, modelo_para_csv


def _csv(*linhas: str) -> bytes:
    return ("\ufeff" + "\r\n".join(linhas) + "\r\n").encode("utf-8")


CAB = "ordem_id;uc_id;motivo;tipo;energia_recuperada_kwh;observacoes"


def test_le_linha_valida_com_numero_no_formato_brasileiro():
    [linha] = ler_planilha(_csv(CAB, "1;UC100001;x;Fraude;1.234,5;medidor violado"))
    assert linha.erro is None
    assert (linha.ordem_id, linha.tipo, linha.energia_recuperada_kwh) == (1, "fraude", 1234.5)
    assert linha.observacoes == "medidor violado"


def test_aceita_nomes_do_dia_a_dia_e_sem_acento():
    linhas = ler_planilha(_csv(CAB, "1;;;Ligação clandestina;10;", "2;;;gato;5;", "3;;;Erro de leitura;;", "4;;;sem irregularidade;;"))
    assert [l.tipo for l in linhas] == ["ligacao_clandestina", "ligacao_clandestina", "erro_leitura", "nenhuma"]


def test_linha_do_modelo_sem_preenchimento_e_ignorada_e_nao_e_erro():
    [linha] = ler_planilha(_csv(CAB, "3;UC100003;motivo;;;"))
    assert linha.pendente and linha.erro is None


def test_observacao_sem_tipo_e_erro():
    [linha] = ler_planilha(_csv(CAB, "3;UC100003;motivo;;;cliente ausente"))
    assert not linha.pendente and "tipo em branco" in linha.erro


@pytest.mark.parametrize("linha, trecho", [
    ("abc;;;fraude;;", "ordem_id inválido"),
    ("1;;;estranho;;", "desconhecido"),
    ("1;;;fraude;-5;", "negativa"),
    ("1;;;fraude;muito;", "inválida"),
    ("1;;;nenhuma;10;", "nenhuma"),
])
def test_linhas_com_erro_trazem_o_motivo(linha, trecho):
    [resultado] = ler_planilha(_csv(CAB, linha))
    assert trecho in resultado.erro


def test_ordem_repetida_vale_so_a_primeira():
    primeira, segunda = ler_planilha(_csv(CAB, "5;;;fraude;1;", "5;;;nenhuma;;"))
    assert primeira.erro is None
    assert "mais de uma vez" in segunda.erro


def test_numero_da_linha_conta_o_cabecalho():
    linhas = ler_planilha(_csv(CAB, "1;;;fraude;;", ";;;;;", "2;;;fraude;;"))
    assert [l.linha for l in linhas] == [2, 4]  # a linha 3 estava em branco


def test_aceita_virgula_como_separador_e_latin1():
    [linha] = ler_planilha("Ordem,Tipo,kWh\n9,Erro de leitura,12.5\n".encode("latin-1"))
    assert (linha.ordem_id, linha.tipo, linha.energia_recuperada_kwh) == (9, "erro_leitura", 12.5)


@pytest.mark.parametrize("conteudo", [b"", b"   \n", b"a;b\n1;2\n"])
def test_arquivo_inutilizavel_levanta_planilha_invalida(conteudo):
    with pytest.raises(PlanilhaInvalida):
        ler_planilha(conteudo)


def test_modelo_neutraliza_formula_e_tem_uma_linha_por_ordem():
    texto = modelo_para_csv([{"id": 3, "uc_id": "UC100003", "motivo": "=cmd()"}, {"id": 4, "uc_id": "UC100004", "motivo": None}])
    assert texto.startswith("\ufeffordem_id;uc_id;motivo;tipo")
    assert "'=cmd()" in texto
    assert texto.count("\r\n") == 3
