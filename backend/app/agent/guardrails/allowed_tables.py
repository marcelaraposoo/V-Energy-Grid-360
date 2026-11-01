# Tabelas do contrato Gold que o agente pode consultar.
# fato_segmento_mensal fica de fora de propósito (decisão do contrato).
ALLOWED_TABLES = frozenset(
    {
        "dim_uc",
        "fato_consumo_faturamento",
        "receita_decomposicao",
        "kpis_mensal",
        "dec_fec_alimentador_mensal",
        "fato_interrupcao",
        "fato_atendimento",
        "fato_troca_medidor",
        "fila_inspecao",
    }
)
