# Contrato esperado da camada Gold (rascunho do time Dev)

O backend define o que **precisa** da Gold. Quando a frente de Dados fechar o modelo, comparar com esta lista
e ajustar `app/repositories/sqlite_repo.py` (ou pedir ajuste na Gold). Colunas abaixo = o que o mock já usa.

| Tabela sugerida | Colunas usadas pelo portal | Usada em |
|---|---|---|
| `gold_unidades_consumidoras` | uc_id, titular, classe, municipio, bairro, alimentador_id, status, data_ligacao | busca, visão 360, filtros |
| `gold_faturamento_mensal` (grão UC × competência) | uc_id, competencia (YYYY-MM), consumo_kwh, valor, bandeira, vencimento, status (paga/aberta/atrasada) + municipio, bairro, classe | dashboard, receita (preço × volume), visão 360 |
| `gold_medidores` | uc_id, medidor_id, tipo, data_instalacao, ultima_manutencao, status | visão 360 |
| `gold_geracao_distribuida` | uc_id, potencia_kwp, data_conexao | visão 360, fila de perdas |
| `gold_ocorrencias_rede` | alimentador_id, municipio, data, competencia, ucs_afetadas, duracao_h, causa | DEC/FEC, visão 360 |
| `gold_dec_fec_alimentador_mes` | alimentador_id, competencia, dec, fec, ucs_total | continuidade (se vier pré-calculado, dispensa o cálculo no backend) |
| `gold_atendimentos` | uc_id, protocolo, data, canal, assunto, status, nota_satisfacao | visão 360 |
| `gold_suspeitas_perdas` | uc_id, motivos, probabilidade, energia_recuperavel_kwh_mes | fila de inspeção |

Pontos a alinhar com a frente de Dados:
1. `competencia` como texto `YYYY-MM`?
2. A Gold já terá município/bairro/classe desnormalizados na tabela de faturamento?
3. Quem calcula DEC/FEC (Gold ou backend)? Quem calcula o score de suspeita?
4. `ordens_inspecao` é do portal (não da Gold): será criada no SQLite do backend.
