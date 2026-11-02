"""Colunas da Gold consolidada: A5 (empresa/mês) e A3 (segmento/mês).

As leituras preservam o grão e os nomes da Gold. Não somam meses, calculam
comparações de períodos nem completam competências ausentes com zeros.
"""

COLUNAS_KPIS = (
    "mes_referencia", "qtd_ucs_cadastradas", "qtd_ucs_faturadas", "consumo_total_kwh",
    "receita_energia", "receita_total", "preco_medio_kwh", "bandeira_predominante",
    "pct_faturas_bandeira_nao_verde", "qtd_faturas_em_aberto", "inadimplencia_pct",
    "valor_em_aberto_mais_90_dias", "qtd_ucs_com_gd", "qtd_interrupcoes", "dec_horas",
    "fec", "qtd_atendimentos", "nota_satisfacao_media", "variacao_consumo_ano_anterior_pct",
    "variacao_receita_ano_anterior_pct",
)

COLUNAS_SEGMENTOS = (
    "mes_referencia", "municipio", "bairro", "classe", "qtd_ucs_cadastradas",
    "qtd_ucs_faturadas", "qtd_ucs_com_gd", "consumo_kwh", "consumo_kwh_ucs_com_gd",
    "receita_energia", "receita_total", "qtd_faturas", "qtd_faturas_em_aberto",
    "valor_em_aberto", "qtd_faturas_bandeira_nao_verde", "qtd_trocas_medidor",
)

COLUNAS_TEXTO = {"mes_referencia", "municipio", "bairro", "classe", "bandeira_predominante"}


def validar_filtro_bairro(municipio: str | None, bairro: str | None) -> None:
    if bairro is not None and municipio is None:
        raise ValueError("O filtro por bairro exige município: a chave é municipio + bairro.")
