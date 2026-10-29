"""Monta um `gold.db` minúsculo, só com a `dim_uc`, no formato do notebook 03_gold_dim_uc.

Os testes do repositório SQLite usam este arquivo em vez do banco real (que ainda não está no repositório).
Se a `dim_uc` ganhar colunas, acrescente em COLUNAS e em `_uc`.
"""
from __future__ import annotations

import sqlite3

COLUNAS = [
    "id_uc", "nome_titular_mascarado", "documento_mascarado", "tipo_pessoa",
    "logradouro", "numero", "bairro", "municipio", "uf", "cep", "latitude", "longitude",
    "classe", "subgrupo_tarifario", "alimentador", "data_ligacao", "data_ligacao_estimada", "status",
    "id_medidor_ativo", "tipo_medidor_ativo", "modelo_medidor_ativo", "data_instalacao_medidor",
    "idade_medidor_anos", "medidor_trocado_recentemente",
    "possui_gd", "potencia_gd_kwp", "data_conexao_gd", "modalidade_gd",
    "energia_injetada_media_kwh", "energia_injetada_atipica",
    "primeiro_mes_leitura", "ultimo_mes_leitura",
    "consumo_medio_12m_kwh", "consumo_medio_12m_anterior_kwh", "variacao_consumo_12m_pct",
]


def _uc(id_uc: str, **extra) -> dict:
    base = dict(
        id_uc=id_uc, nome_titular_mascarado="MARIA S***", documento_mascarado="***.123.456-**", tipo_pessoa="PF",
        logradouro="RUA A", numero="10", bairro="BOA VIAGEM", municipio="RECIFE", uf="PE", cep="51020000",
        latitude=-8.1, longitude=-34.9, classe="RESIDENCIAL", subgrupo_tarifario="B1", alimentador="AL001",
        data_ligacao="2015-03-01", data_ligacao_estimada=0, status="ATIVA",
        id_medidor_ativo=f"M-{id_uc}", tipo_medidor_ativo="ELETRONICO", modelo_medidor_ativo="X1",
        data_instalacao_medidor="2020-01-10", idade_medidor_anos=6.5, medidor_trocado_recentemente=0,
        possui_gd=0, potencia_gd_kwp=None, data_conexao_gd=None, modalidade_gd=None,
        energia_injetada_media_kwh=None, energia_injetada_atipica=0,
        primeiro_mes_leitura="2022-07", ultimo_mes_leitura="2026-06",
        consumo_medio_12m_kwh=180.5, consumo_medio_12m_anterior_kwh=200.0, variacao_consumo_12m_pct=-9.75,
    )
    base.update(extra)
    return base


# Cobre: GD normal, GD atípica com booleano em texto, mesmo bairro em dois municípios, UC sem medidor,
# nome com acento, e um alimentador (AL002) que atende dois municípios.
UCS = [
    _uc("UC00001", nome_titular_mascarado="JOAO S***", possui_gd=1, potencia_gd_kwp=5.5,
        data_conexao_gd="2024-02-10", modalidade_gd="AUTOCONSUMO LOCAL", energia_injetada_media_kwh=220.0),
    _uc("UC00002", nome_titular_mascarado="JOSÉ A***", classe="COMERCIAL", municipio="OLINDA", bairro="CENTRO",
        alimentador="AL002", possui_gd="true", potencia_gd_kwp=9.9, data_conexao_gd="2026-01-05",
        modalidade_gd="AUTOCONSUMO REMOTO", energia_injetada_media_kwh=1089.0, energia_injetada_atipica="true"),
    _uc("UC00003", nome_titular_mascarado="ANA P***", classe="PODER PUBLICO", bairro="CENTRO", id_medidor_ativo=None),
    _uc("UC00004", nome_titular_mascarado="LUIZ M***", municipio="OLINDA", bairro="CENTRO", alimentador="AL002"),
    _uc("UC00005", nome_titular_mascarado="PAULO R***", classe="RURAL", municipio="PAULISTA", bairro="JANGA",
        alimentador="AL002"),
    _uc("UC00006", nome_titular_mascarado="CARLA T***", classe="INDUSTRIAL", alimentador="AL003"),
]


def criar_gold_db(caminho, ucs=None, colunas=None) -> str:
    """Cria o SQLite em `caminho` e devolve o caminho como texto."""
    ucs = UCS if ucs is None else ucs
    colunas = COLUNAS if colunas is None else colunas
    con = sqlite3.connect(str(caminho))
    con.execute(f"CREATE TABLE dim_uc ({', '.join(colunas)})")
    for uc in ucs:
        con.execute(
            f"INSERT INTO dim_uc ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})",
            [uc.get(c) for c in colunas],
        )
    con.commit()
    con.close()
    return str(caminho)
