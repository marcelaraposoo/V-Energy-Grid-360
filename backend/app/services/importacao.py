"""Importação em lote dos resultados de inspeção: a planilha (CSV) que a equipe de campo preenche.

Este módulo só lê e valida o arquivo; quem registra cada resultado é o serviço `perdas`. Assim, uma linha
com erro não derruba as demais: cada linha vira um `LinhaPlanilha` aceita ou rejeitada com o motivo.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass

TAMANHO_MAXIMO = 1_000_000  # bytes
LINHAS_MAXIMAS = 5_000
TIPOS = ("fraude", "ligacao_clandestina", "erro_leitura", "erro_cadastro", "nenhuma")
# Como a equipe costuma escrever: sem acento, com espaço, ou com o nome curto.
_SINONIMOS_TIPO = {
    "fraude": "fraude", "fraude_no_medidor": "fraude",
    "ligacao_clandestina": "ligacao_clandestina", "gato": "ligacao_clandestina", "furto": "ligacao_clandestina",
    "erro_leitura": "erro_leitura", "erro_de_leitura": "erro_leitura",
    "erro_cadastro": "erro_cadastro", "erro_de_cadastro": "erro_cadastro",
    "nenhuma": "nenhuma", "nenhum": "nenhuma", "sem_irregularidade": "nenhuma", "regular": "nenhuma",
}
_COLUNAS = {
    "ordem_id": {"ordem_id", "ordem", "id", "id_ordem", "n_ordem"},
    "tipo": {"tipo", "tipo_irregularidade", "resultado"},
    "energia_recuperada_kwh": {"energia_recuperada_kwh", "kwh_recuperado", "energia_kwh", "kwh"},
    "observacoes": {"observacoes", "observacao", "obs"},
}


class PlanilhaInvalida(Exception):
    """O arquivo inteiro não pode ser lido (vazio, grande demais, sem as colunas obrigatórias)."""


@dataclass
class LinhaPlanilha:
    linha: int  # número da linha no arquivo (o cabeçalho é a linha 1)
    ordem_id: int | None = None
    tipo: str | None = None
    energia_recuperada_kwh: float = 0.0
    observacoes: str | None = None
    erro: str | None = None
    pendente: bool = False  # linha do modelo que a equipe ainda não preencheu: é ignorada, não é erro


def _normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return "_".join(sem_acento.casefold().replace("-", " ").split())


def _decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("latin-1")  # Excel antigo salva CSV em Windows-1252


def _numero(texto: str) -> float:
    """Aceita 1234.5, 1234,5 e 1.234,5 (formato brasileiro)."""
    t = texto.strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def _coluna(cabecalho: list[str], nome: str) -> int | None:
    for i, c in enumerate(cabecalho):
        if _normalizar(c) in _COLUNAS[nome]:
            return i
    return None


def ler_planilha(conteudo: bytes) -> list[LinhaPlanilha]:
    if not conteudo.strip():
        raise PlanilhaInvalida("O arquivo está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise PlanilhaInvalida("O arquivo é grande demais (limite de 1 MB).")
    texto = _decodificar(conteudo)
    primeira = texto.splitlines()[0] if texto.splitlines() else ""
    separador = max((";", ",", "\t"), key=primeira.count)
    linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=separador))
    cabecalho = linhas[0]
    i_ordem, i_tipo = _coluna(cabecalho, "ordem_id"), _coluna(cabecalho, "tipo")
    if i_ordem is None or i_tipo is None:
        raise PlanilhaInvalida("O cabeçalho precisa ter as colunas 'ordem_id' e 'tipo'. Use o modelo do portal.")
    i_kwh, i_obs = _coluna(cabecalho, "energia_recuperada_kwh"), _coluna(cabecalho, "observacoes")
    dados = linhas[1:]
    if len(dados) > LINHAS_MAXIMAS:
        raise PlanilhaInvalida(f"A planilha tem linhas demais (limite de {LINHAS_MAXIMAS}).")

    def celula(linha: list[str], i: int | None) -> str:
        return linha[i].strip() if i is not None and i < len(linha) else ""

    resultado: list[LinhaPlanilha] = []
    for n, bruta in enumerate(dados, start=2):
        if not any(c.strip() for c in bruta):
            continue  # linha em branco
        item = LinhaPlanilha(linha=n)
        resultado.append(item)
        try:
            item.ordem_id = int(celula(bruta, i_ordem).lstrip("#"))
        except ValueError:
            item.erro = "ordem_id inválido: informe o número da ordem."
            continue
        tipo_bruto = celula(bruta, i_tipo)
        if not tipo_bruto:
            if celula(bruta, i_kwh) or celula(bruta, i_obs):
                item.erro = "tipo em branco: informe o que foi encontrado em campo."
            else:
                item.pendente = True
            continue
        tipo = _SINONIMOS_TIPO.get(_normalizar(tipo_bruto))
        if tipo is None:
            item.erro = f"tipo '{tipo_bruto}' desconhecido. Use: {', '.join(TIPOS)}."
            continue
        item.tipo = tipo
        kwh_bruto = celula(bruta, i_kwh)
        if kwh_bruto:
            try:
                item.energia_recuperada_kwh = _numero(kwh_bruto)
            except ValueError:
                item.erro = f"energia_recuperada_kwh inválida: '{kwh_bruto}'."
                continue
            if item.energia_recuperada_kwh < 0:
                item.erro = "energia_recuperada_kwh não pode ser negativa."
                continue
        if tipo == "nenhuma" and item.energia_recuperada_kwh:
            item.erro = "tipo 'nenhuma' não pode ter energia recuperada."
            continue
        item.observacoes = celula(bruta, i_obs)[:500] or None
    # ordem repetida: vale só a primeira linha (a segunda seria rejeitada de qualquer forma, pois a ordem já concluiu)
    vistas: set[int] = set()
    for item in resultado:
        if item.erro or item.pendente or item.ordem_id is None:
            continue
        if item.ordem_id in vistas:
            item.erro = f"ordem #{item.ordem_id} aparece mais de uma vez na planilha."
        vistas.add(item.ordem_id)
    return resultado


def _texto(valor: str) -> str:
    """Neutraliza injeção de fórmula no Excel (= + - @ no início da célula)."""
    return "'" + valor if valor.startswith(("=", "+", "-", "@", "\t", "\r")) else valor


def modelo_para_csv(ordens: list[dict]) -> str:
    """Modelo para a equipe de campo: uma linha por ordem em aberto, com as colunas de resultado vazias."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(["ordem_id", "uc_id", "motivo", "tipo", "energia_recuperada_kwh", "observacoes"])
    for o in ordens:
        escritor.writerow([o["id"], o["uc_id"], _texto(o.get("motivo") or ""), "", "", ""])
    return "\ufeff" + saida.getvalue()
