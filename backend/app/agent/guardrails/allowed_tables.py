# Tabelas do contrato Gold que o agente pode consultar.
# Inclui o agregado mensal validado no contrato físico da Gold.
ALLOWED_TABLES = frozenset(
    {
        "dim_uc",
        "fato_consumo_faturamento",
        "fato_segmento_mensal",
        "receita_decomposicao",
        "kpis_mensal",
        "dec_fec_alimentador_mensal",
        "fato_interrupcao",
        "fato_atendimento",
        "fato_troca_medidor",
        "fila_inspecao",
    }
)
