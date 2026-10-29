# Dicionário de dados da camada Gold

Um arquivo por tabela, com: para que serve, o grão, as colunas (definição e tipo), as **decisões de limpeza** que afetam os números e os **cuidados de uso**. As definições das colunas seguem o contrato da Gold; as decisões de limpeza, o `docs/data_quality_log.md`.

Cada integrante escreve as tabelas das Silvers que conhece.  (`dim_uc`, `fato_segmento_mensal`, `fato_troca_medidor`, `fato_interrupcao` e `dec_fec_alimentador_mensal`) entram na mesma pasta, no mesmo formato.

| Tabela | Contrato | Colunas | Status |
|---|---|---|---|
| [`fato_consumo_faturamento`](fato_consumo_faturamento.md) | A2 | 31 | executada, todas as checagens PASS |
| [`fato_atendimento`](fato_atendimento.md) | B1 | 16 | executada, todas as checagens PASS |
| [`receita_decomposicao`](receita_decomposicao.md) | A4 | 24 | executada, todas as checagens PASS |
| [`fila_inspecao`](fila_inspecao.md) | B2 | 20 | executada, todas as checagens PASS |
| [`kpis_mensal`](kpis_mensal.md) | A5 | 20 | executada, todas as checagens PASS |
