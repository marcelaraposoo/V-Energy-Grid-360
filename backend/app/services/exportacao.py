"""Exportação da fila de suspeitas para planilha: CSV que abre direto no Excel em português."""
from __future__ import annotations

import csv
import io

BOM = "\ufeff"  # sem o BOM o Excel não reconhece UTF-8 e estraga os acentos
CABECALHO = ["Posição", "UC", "Titular", "Município", "Bairro", "Classe", "Motivos", "Probabilidade",
             "Energia recuperável (kWh/mês)", "Prioridade"]
_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _texto(valor: str) -> str:
    """Neutraliza injeção de fórmula: no Excel, texto começando com = + - @ é executado como fórmula.
    O apóstrofo na frente impede isso (e fica visível na célula)."""
    return "'" + valor if valor.startswith(_INICIO_DE_FORMULA) else valor


def _num(valor: float, casas: int) -> str:
    """Vírgula decimal: é o que o Excel em português lê como número (com ponto, viraria texto ou data)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def fila_para_csv(itens) -> str:
    """Itens da fila (`SuspeitaFila`) -> texto CSV: separador `;`, UTF-8 com BOM, linhas terminadas em CRLF."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow(CABECALHO)
    for i in itens:
        escritor.writerow([
            i.posicao, i.uc_id, _texto(i.titular), _texto(i.municipio), _texto(i.bairro), i.classe,
            _texto(" | ".join(i.motivos)), _num(i.probabilidade, 2),
            _num(i.energia_recuperavel_kwh_mes, 1), _num(i.prioridade_score, 1),
        ])
    return BOM + saida.getvalue()
