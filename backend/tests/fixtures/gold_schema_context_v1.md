# V-Energy Grid 360 — Contexto Gold v1 para o Agente

Este documento representa o contrato de dados Gold v1 utilizado pelo agente para geração de SQL.

Utilize exclusivamente as tabelas, colunas, relacionamentos e definições descritos abaixo.

Não invente tabelas, colunas, métricas ou relacionamentos ausentes deste contexto.

## Banco

- Dialeto SQL: SQLite
- Nomes de tabelas e colunas: `snake_case`
- `mes_referencia`: texto no formato `yyyy-MM`
- Datas seguem os campos explicitamente definidos em cada tabela

## Regras semânticas importantes

### Bairro

O mesmo nome de bairro pode existir em municípios diferentes.

Quando uma pergunta envolver um bairro específico, utilize `municipio` junto com `bairro` sempre que o município estiver disponível no contexto da pergunta.

Não trate `bairro` isoladamente como identificador global.

### Períodos do diagnóstico

Quando a pergunta utilizar os períodos definidos pelo diagnóstico:

- `PRIMEIRO_ANO`: `2022-07` até `2023-06`
- `ULTIMOS_12M`: `2025-07` até `2026-06`

Não interprete esses nomes utilizando a data atual.

### Linguagem de negócio

Considere equivalências semânticas como:

- UC = unidade consumidora
- conta de luz = fatura / faturamento
- falta de luz = interrupção no fornecimento
- painel solar = geração distribuída / GD
- consumo = energia consumida em kWh
- receita = informação financeira de faturamento, observando as definições disponíveis no schema
- DEC e FEC = indicadores de qualidade do serviço

---

# 1. `dim_uc`

## Grão

1 linha = 1 unidade consumidora.

## Uso

Informações cadastrais e características atuais da UC.

Pode ser utilizada para filtros por:

- município;
- bairro;
- classe;
- geração distribuída;
- medidor;
- alimentador.

## Colunas

- `id_uc` — texto — identificador da unidade consumidora
- `nome_titular_mascarado` — texto
- `documento_mascarado` — texto
- `tipo_pessoa` — texto — `PF` ou `PJ`
- `logradouro` — texto
- `numero` — texto
- `bairro` — texto
- `municipio` — texto
- `uf` — texto
- `cep` — texto
- `latitude` — decimal
- `longitude` — decimal
- `classe` — texto — `RESIDENCIAL`, `RURAL`, `COMERCIAL`, `PODER PUBLICO` ou `INDUSTRIAL`
- `subgrupo_tarifario` — texto
- `alimentador` — texto
- `data_ligacao` — data
- `data_ligacao_estimada` — booleano
- `status` — texto
- `id_medidor_ativo` — texto
- `tipo_medidor_ativo` — texto
- `modelo_medidor_ativo` — texto
- `data_instalacao_medidor` — data
- `idade_medidor_anos` — decimal
- `medidor_trocado_recentemente` — booleano
- `possui_gd` — booleano — indica geração distribuída/painel solar
- `potencia_gd_kwp` — decimal
- `data_conexao_gd` — data
- `modalidade_gd` — texto
- `energia_injetada_media_kwh` — decimal
- `primeiro_mes_leitura` — texto
- `ultimo_mes_leitura` — texto

---

# 2. `fato_consumo_faturamento`

## Grão

1 linha = 1 UC em 1 mês de referência.

## Uso

Principal tabela para perguntas sobre:

- consumo;
- faturamento;
- faturas em aberto;
- conta alta;
- comparação com ano anterior;
- consumo por município, bairro, classe ou período.

## Colunas

- `id_uc` — texto
- `mes_referencia` — texto — `yyyy-MM`
- `ano` — inteiro
- `mes` — inteiro
- `periodo_diagnostico` — texto — `PRIMEIRO_ANO`, `ULTIMOS_12M` ou `OUTRO`
- `classe` — texto
- `bairro` — texto
- `municipio` — texto
- `id_medidor` — texto
- `data_leitura` — data
- `tipo_leitura` — texto — `REAL` ou `ESTIMADA`
- `consumo_kwh` — inteiro
- `consumo_kwh_ano_anterior` — inteiro
- `variacao_consumo_ano_anterior_pct` — decimal
- `troca_medidor` — booleano
- `consumo_corrigido` — booleano
- `leitura_anterior_ausente` — booleano
- `id_fatura` — texto
- `data_emissao` — data
- `data_vencimento` — data
- `data_pagamento` — data
- `valor_energia` — decimal — valor da energia sem tributos
- `tributos` — decimal
- `valor_total` — decimal — valor total da fatura
- `bandeira_tarifaria` — texto
- `status_fatura` — texto — `PAGA` ou `EM ABERTO`
- `em_aberto` — booleano
- `dias_atraso` — inteiro
- `preco_medio_kwh` — decimal — `valor_energia / consumo_kwh`

---

# 3. `receita_decomposicao`

## Grão

1 linha = 1 combinação de município × bairro × classe.

A tabela compara diretamente:

- primeiro ano;
- últimos 12 meses.

## Uso

Utilize para perguntas sobre:

- variação de receita;
- variação de volume;
- efeito preço;
- efeito volume;
- comparação entre município, bairro e classe.

## Colunas

- `municipio` — texto
- `bairro` — texto
- `classe` — texto
- `qtd_ucs_periodo_0` — inteiro
- `qtd_ucs_periodo_1` — inteiro
- `volume_kwh_0` — decimal
- `volume_kwh_1` — decimal
- `receita_0` — decimal
- `receita_1` — decimal
- `preco_medio_0` — decimal
- `preco_medio_1` — decimal
- `variacao_receita` — decimal
- `variacao_receita_pct` — decimal
- `variacao_volume_pct` — decimal
- `efeito_preco` — decimal
- `efeito_volume` — decimal
- `consumo_medio_uc_0` — decimal
- `consumo_medio_uc_1` — decimal
- `qtd_ucs_com_gd_1` — inteiro
- `qtd_trocas_medidor_1` — inteiro

## Fórmulas do contrato

- `efeito_volume = (V1 - V0) × P0`
- `efeito_preco = (P1 - P0) × V1`

A soma dos efeitos representa a variação da receita.

## Atenção

A definição definitiva de receita utilizada pelo negócio ainda pode depender de decisão entre `valor_energia` e `valor_total`.

Não invente uma definição caso a pergunta exija essa distinção e o contexto não a resolva.

---

# 4. `kpis_mensal`

## Grão

1 linha = 1 mês de referência.

## Uso

Indicadores gerais do negócio e comparações mensais.

## Colunas

- `mes_referencia` — texto — `yyyy-MM`
- `qtd_ucs_faturadas` — inteiro
- `consumo_total_kwh` — decimal
- `receita_energia` — decimal
- `receita_total` — decimal
- `preco_medio_kwh` — decimal
- `bandeira_predominante` — texto
- `qtd_faturas_em_aberto` — inteiro
- `inadimplencia_pct` — decimal
- `qtd_ucs_com_gd` — inteiro
- `dec_horas` — decimal
- `fec` — decimal
- `qtd_atendimentos` — inteiro
- `nota_satisfacao_media` — decimal
- `variacao_consumo_ano_anterior_pct` — decimal
- `variacao_receita_ano_anterior_pct` — decimal

---

# 5. `dec_fec_alimentador_mensal`

## Grão

1 linha = 1 alimentador em 1 mês.

## Uso

Perguntas sobre:

- DEC;
- FEC;
- qualidade do serviço;
- alimentadores com pior desempenho;
- interrupções por região;
- causa principal.

## Colunas

- `alimentador` — texto
- `municipio` — texto
- `mes_referencia` — texto — `yyyy-MM`
- `qtd_ucs_alimentador` — inteiro
- `qtd_interrupcoes` — inteiro
- `horas_interrompidas` — decimal
- `dec_horas` — decimal
- `fec` — decimal
- `causa_principal` — texto
- `ranking_dec_mes` — inteiro — `1` representa o pior DEC do mês

---

# 6. `fato_interrupcao`

## Grão

1 linha = 1 UC afetada por 1 interrupção. Não é 1 queda.

Uma queda de 2 horas que atinge 100 UCs gera 100 linhas, cada uma com `duracao_min` = 120.

## Como interpretar (importante)

- `duracao_min` é o tempo que **aquela UC** ficou sem energia.
- Somar `duracao_min` não dá a duração de uma queda: dá o impacto acumulado em **horas-cliente** (no exemplo, 100 UCs x 2 h = 200 horas-cliente). Use a soma apenas quando a pergunta for sobre impacto total, e chame o resultado de horas-cliente.
- "Quanto tempo durou a falta de luz": use a duração de cada interrupção (média, mínimo ou máximo de `duracao_min`), nunca a soma, e deixe claro que o valor é por UC afetada.
- "Quantas UCs ficaram sem luz": use `COUNT(DISTINCT id_uc)`, nunca `COUNT(*)`, porque uma UC pode aparecer em várias interrupções.
- "Quantas quedas houve": este contrato não identifica a queda com segurança. Não use `COUNT(*)` como número de quedas e não presuma que `id_ocorrencia` agrupa as UCs da mesma queda. Se a pergunta exigir isso, use `INSUFFICIENT_CONTEXT`.
- Para DEC e FEC e para o ranking de alimentadores, prefira `dec_fec_alimentador_mensal`, que já está calculada.

## Uso

Perguntas sobre:

- falta de luz;
- interrupções por UC;
- interrupções por bairro;
- interrupções por município;
- alimentador;
- causa;
- duração.

## Colunas

- `id_ocorrencia` — texto
- `id_uc` — texto
- `alimentador` — texto
- `bairro` — texto
- `municipio` — texto
- `tipo` — texto
- `causa` — texto
- `data_inicio` — data
- `data_fim` — data
- `mes_referencia` — texto — `yyyy-MM`
- `duracao_min` — inteiro

---

# 7. `fato_atendimento`

## Grão

1 linha = 1 chamado/protocolo.

## Uso

Perguntas sobre:

- chamados;
- atendimento;
- assunto;
- status de abertura;
- tempo de resolução;
- satisfação.

## Colunas

- `protocolo` — texto
- `id_uc` — texto
- `canal` — texto
- `assunto` — texto
- `subassunto` — texto
- `data_abertura` — data
- `data_fechamento` — data
- `mes_referencia` — texto — `yyyy-MM`
- `aberto` — booleano
- `tempo_resolucao_horas` — decimal
- `qtd_tratativas` — inteiro
- `ultima_acao` — texto
- `nota_satisfacao` — decimal

---

# Relacionamentos disponíveis

Quando for necessário relacionar informações por unidade consumidora, utilize `id_uc` somente entre tabelas que possuam esse campo.

Principais tabelas com `id_uc`:

- `dim_uc`
- `fato_consumo_faturamento`
- `fato_interrupcao`
- `fato_atendimento`

Não invente relacionamento entre tabelas agregadas quando o contrato não fornecer uma chave adequada.

Para análises já agregadas por município, bairro e classe, prefira utilizar diretamente `receita_decomposicao` em vez de reconstruir desnecessariamente a mesma agregação.

---

# Limitações conhecidas deste contrato

## Variação de consumo por UC em dois períodos de 12 meses

O contrato atual ainda não possui diretamente, na `dim_uc`:

- `consumo_medio_12m_kwh`;
- `consumo_medio_12m_anterior_kwh`;
- `variacao_consumo_12m_pct`.

Portanto, perguntas que dependam especificamente desses campos não devem assumir que eles existem.

Utilize dados existentes somente quando a comparação puder ser construída com segurança a partir de `fato_consumo_faturamento`.

Caso contrário, utilize `INSUFFICIENT_CONTEXT`.

## Manutenção preventiva

O contrato possui informações sobre interrupções, causas, DEC e FEC.

Entretanto, não existe ainda uma métrica definitiva que determine diretamente o retorno de manutenção preventiva.

Não invente essa métrica.

## Receita

Existem:

- `valor_energia`;
- `valor_total`;
- `receita_energia`;
- `receita_total`.

Se a pergunta depender de uma definição específica de receita e o contexto não permitir determinar qual definição o usuário deseja, utilize `NEEDS_CLARIFICATION`.

---

# Regras finais para geração SQL

1. Utilize somente tabelas e colunas presentes neste documento.
2. Não invente relacionamentos.
3. Não invente métricas.
4. Não invente filtros.
5. Utilize `municipio` junto com `bairro` quando necessário para evitar ambiguidade.
6. Respeite os períodos de diagnóstico definidos neste contexto.
7. Prefira tabelas agregadas quando elas responderem diretamente à pergunta.
8. Utilize tabelas de fato quando a pergunta exigir granularidade de UC, mês, ocorrência ou chamado.
9. Se faltar uma informação objetiva que o usuário possa fornecer, utilize `NEEDS_CLARIFICATION`.
10. Se o dado ou estrutura necessária não existir neste contrato, utilize `INSUFFICIENT_CONTEXT`.