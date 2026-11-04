# Tabelas do contrato Gold que o agente pode consultar.
# Agregado aditivo reconciliado com a fonte no grão mês/município/bairro/classe.
ALLOWED_TABLES = frozenset(
    {
        "dim_uc",
        "fato_segmento_mensal",
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
