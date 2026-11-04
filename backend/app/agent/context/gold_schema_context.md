# V-Energy Grid 360 — Contexto Gold para o Agente

Este documento descreve o recorte do schema físico Gold utilizado pelo agente para geração de SQL, com semântica do dicionário oficial da Gold.

Use exclusivamente as tabelas, colunas e relacionamentos descritos abaixo; não invente nenhum.

## Banco

- Dialeto SQL: SQLite. `mes_referencia` é texto `yyyy-MM`.
- Datas e timestamps são `TEXT`, booleanos `INTEGER` (0/1), decimais `REAL`.
- Janela de competências: `2022-07` a `2026-06`; não use a data atual como fim da base.

### Datas e timestamps

Datas usam `yyyy-MM-dd`; timestamps locais, sem fuso, usam `yyyy-MM-dd HH:mm:ss`.
Competência (`mes_referencia`) não é emissão, vencimento nem pagamento.
Para um mês de timestamps, prefira intervalo semiaberto:
`campo >= '2026-06-01 00:00:00' AND campo < '2026-07-01 00:00:00'`.
Evite `campo <= '2026-06-30'`, que excluiria registros com horário nesse dia.

## Regras semânticas importantes

### Bairro

O mesmo bairro pode existir em municípios diferentes: use `municipio` junto com `bairro` quando o município estiver disponível. Não trate `bairro` como identificador global.

### Classe de consumo

Quando a pergunta citar uma classe de consumo (comercial, residencial, rural, poder público ou industrial), filtre obrigatoriamente por `classe` usando o valor exato: `COMERCIAL`, `RESIDENCIAL`, `RURAL`, `PODER PUBLICO` ou `INDUSTRIAL`. Nunca agregue todas as classes quando a pergunta menciona uma. Exemplo: "receita comercial em Olinda" exige `classe = 'COMERCIAL'`.

Ao agregar `receita_decomposicao`, use `SUM(...)` apenas para medidas aditivas, como receitas e volumes. Preços, percentuais, razões e efeitos derivados não devem ser somados diretamente; quando a granularidade mudar, recalcule-os a partir das bases agregadas conforme as regras de decomposição.

### Nomes de municípios

Os nomes de municípios têm acentuação e usam capitalização normal (por exemplo `Jaboatão dos Guararapes`, `São Lourenço da Mata`, `Araçoiaba`). Use exatamente essa grafia nos filtros.

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

1 linha = 1 unidade consumidora, cadastro atual.

## Uso

Informações cadastrais e características atuais da UC; não trate atributos atuais como histórico mensal.

Pode ser utilizada para filtros por:

- município;
- bairro;
- classe;
- geração distribuída;
- medidor;
- alimentador.

## Atenção: energia injetada

Ao somar, calcular média ou comparar `energia_injetada_media_kwh`, ignore as UCs com `energia_injetada_atipica = 1` (o valor não é confiável). Para apenas contar ou listar UCs com painel solar, `possui_gd` basta e não precisa desse filtro.

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
- `energia_injetada_atipica` — booleano — sinaliza que `energia_injetada_media_kwh` está fora do padrão e **não deve ser usada como medida**. Nunca é nula (`false` para UCs sem GD)
- `primeiro_mes_leitura` — texto
- `ultimo_mes_leitura` — texto
- `consumo_medio_12m_kwh` — decimal — média mensal de `consumo_kwh` de `2025-07` a `2026-06`
- `consumo_medio_12m_anterior_kwh` — decimal — média mensal de `consumo_kwh` de `2024-07` a `2025-06`
- `variacao_consumo_12m_pct` — decimal — `((consumo_medio_12m_kwh / consumo_medio_12m_anterior_kwh) - 1) * 100`, arredondada a 2 casas; nula se a média anterior não for maior que zero

`variacao_consumo_12m_pct` compara as médias de dois períodos de 12 meses por UC. Para comparar um mês com o mesmo mês do ano anterior, use `variacao_consumo_ano_anterior_pct` em `fato_consumo_faturamento`.

Em perguntas sobre queda ou aumento de consumo por UC, ignore as UCs com `variacao_consumo_12m_pct` nula (sem histórico no período anterior).

---

# 2. `fato_consumo_faturamento`

## Grão

1 linha = 1 UC em 1 mês de referência.

`COUNT(*)` conta registros UC-mês; para UCs distintas em vários meses use `COUNT(DISTINCT id_uc)`.

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
- `possui_gd_no_mes` — booleano — se a UC tinha geração distribuída naquele mês
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
- `valor_energia` — decimal — R$, energia sem tributos, com adicional de bandeira embutido; receita do diagnóstico
- `tributos` — decimal
- `valor_total` — decimal — R$, total da fatura com tributos; não confundir com receita de energia
- `bandeira_tarifaria` — texto
- `status_fatura` — texto — `PAGA` ou `EM ABERTO`
- `em_aberto` — booleano — fatura não paga no snapshot
- `dias_atraso` — inteiro — até pagamento ou até `2026-06-30` se em aberto; atraso de fatura paga não é dívida atual
- `faixa_atraso` — texto — `EM DIA`, `ATE 30 DIAS`, `31 A 90 DIAS` ou `MAIS DE 90 DIAS`
- `preco_medio_kwh` — decimal — `valor_energia / consumo_kwh`

### Inadimplência

O percentual financeiro por competência é
`100.0 * SUM(CASE WHEN em_aberto = 1 THEN valor_total ELSE 0 END) / NULLIF(SUM(valor_total), 0)`.
O percentual de faturas em aberto usa contagem de faturas, não valor financeiro.
Não use qualquer `dias_atraso > 0` como inadimplência atual, nem misture dívida antiga com percentual da competência.
Se a pergunta não distinguir estoque de dívida, histórico de atraso ou percentual financeiro/de faturas quando isso for necessário, use `NEEDS_CLARIFICATION`.

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
- `volume_kwh_ucs_com_gd_0` — decimal
- `volume_kwh_ucs_com_gd_1` — decimal
- `pct_faturas_bandeira_nao_verde_0` — decimal
- `pct_faturas_bandeira_nao_verde_1` — decimal
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

Os efeitos de cada linha NÃO são aditivos entre segmentos. Acima do grão
município/bairro/classe (município, classe ou empresa), some primeiro `receita_0`,
`receita_1`, `volume_kwh_0` e `volume_kwh_1`; recalcule `P0 = R0 / V0` e
`P1 = R1 / V1`; então aplique as fórmulas aos totais, protegendo divisão por zero
com `NULLIF`. Não use `SUM(efeito_preco)`/`SUM(efeito_volume)` para representar os efeitos do conjunto.
Variações percentuais e preços médios também devem ser recalculados das bases.

## Atenção

`receita_0` e `receita_1` são somas de `valor_energia`, conforme o dicionário oficial:
energia sem tributos e com bandeira embutida. `efeito_preco` mistura tarifa e bandeira;
o adicional não vem separado e não permite atribuir todo o efeito apenas à tarifa.
`consumo_medio_uc_0/1` mede kWh por UC no período de 12 meses, não média mensal.

---

# 4. `kpis_mensal`

## Grão

1 linha = 1 mês de referência.

## Uso

Indicadores gerais do negócio e comparações mensais.
Para totais e rankings por mês do conjunto inteiro (inclusive meses com maiores
valores faturados), prefira esta tabela agregada quando a métrica existir aqui.
`receita_total` já soma `valor_total` da `fato_consumo_faturamento` por mês;
`receita_energia` soma `valor_energia` e `consumo_total_kwh` soma `consumo_kwh`.
Evite recalcular esses totais varrendo a fato detalhada. Use a fato quando houver
filtros ou dimensões não disponíveis no agregado (por exemplo UC, município ou
classe), preservando o grão e as definições financeiras deste contrato.

## Colunas

- `mes_referencia` — texto — `yyyy-MM`
- `qtd_ucs_cadastradas` — inteiro — UCs ligadas até o fim do mês; base do DEC/FEC geral
- `qtd_ucs_faturadas` — inteiro
- `consumo_total_kwh` — decimal
- `receita_energia` — decimal — R$, soma de `valor_energia` (receita do diagnóstico)
- `receita_total` — decimal — R$, soma de `valor_total`, com tributos
- `preco_medio_kwh` — decimal
- `bandeira_predominante` — texto
- `pct_faturas_bandeira_nao_verde` — decimal — percentual das faturas do mês
- `qtd_faturas_em_aberto` — inteiro
- `inadimplencia_pct` — decimal — percentual do valor total da competência ainda em aberto, não percentual de faturas
- `valor_em_aberto_mais_90_dias` — decimal — R$, desta competência em aberto há mais de 90 dias
- `qtd_ucs_com_gd` — inteiro
- `qtd_interrupcoes` — inteiro — ocorrências-UC, não eventos coletivos
- `dec_horas` — decimal — horas/UC no mês
- `fec` — decimal — interrupções/UC no mês
- `qtd_atendimentos` — inteiro
- `nota_satisfacao_media` — decimal
- `variacao_consumo_ano_anterior_pct` — decimal
- `variacao_receita_ano_anterior_pct` — decimal

Não some preços, percentuais ou médias mensais. Para preço de um período,
use `SUM(receita_energia) / NULLIF(SUM(consumo_total_kwh), 0)`.
Não some contagens mensais de UCs como se fossem UCs distintas do período.

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
- `qtd_ucs_alimentador_mes` — inteiro — UCs ligadas até o fim do mês; denominador mensal
- `qtd_interrupcoes` — inteiro
- `horas_interrompidas` — decimal — horas-cliente (soma das durações por UC em horas)
- `qtd_interrupcoes_evitaveis` — inteiro — ocorrências-UC com causa evitável
- `horas_causas_evitaveis` — decimal — horas-cliente de causas evitáveis; não é retorno financeiro da manutenção
- `dec_horas` — decimal — horas/UC no mês
- `fec` — decimal — interrupções/UC no mês
- `dec_12m_horas` — decimal — soma dos DECs mensais nos 12 meses até este mês; nula antes de `2023-06`
- `fec_12m` — decimal — soma dos FECs mensais nos 12 meses até este mês; nula antes de `2023-06`
- `causa_principal` — texto
- `ranking_dec_mes` — inteiro — `1` representa o pior DEC do mês

### Agregação de DEC/FEC

Para um conjunto de alimentadores no mesmo mês:
`DEC = SUM(horas_interrompidas) / NULLIF(SUM(qtd_ucs_alimentador_mes), 0)`;
`FEC = 1.0 * SUM(qtd_interrupcoes) / NULLIF(SUM(qtd_ucs_alimentador_mes), 0)`.
Não use média simples entre alimentadores nem soma direta de indicadores para agregar regiões.
Para acumular um período, calcule o indicador ponderado em cada mês e depois some os indicadores mensais;
o quociente de numeradores/denominadores somados entre meses representa média mensal ponderada, não DEC/FEC acumulado.
Não some janelas móveis de 12 meses sobrepostas. Não atribua DEC do alimentador a cada bairro.

---

# 6. `fato_interrupcao`

## Grão

1 linha = 1 UC afetada por 1 interrupção. Não é 1 queda.

Uma queda de 2 horas que atinge 100 UCs gera 100 linhas, cada uma com `duracao_min` = 120.

## Como interpretar (importante)

- `duracao_min` é o tempo que **aquela UC** ficou sem energia.
- Somar `duracao_min` não dá a duração de uma queda: dá o impacto acumulado em **tempo-cliente** (no exemplo, 100 UCs x 120 min = 12.000 minutos-cliente, ou 200 horas-cliente). Use a soma apenas quando a pergunta for sobre impacto total. **Respeite a unidade pedida na pergunta**: se pedir minutos, devolva `SUM(duracao_min)` sem converter; só divida por 60 se a pergunta pedir horas.
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
- `classe` — texto
- `causa_evitavel` — booleano — vegetação, falha de equipamento ou sobrecarga; causa nula conta como não evitável, um piso de evitabilidade
- `data_hora_inicio` — data e hora — `yyyy-MM-dd HH:mm:ss`, horário local
- `data_hora_fim` — data e hora — `yyyy-MM-dd HH:mm:ss`, horário local
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
- `municipio` — texto — município da UC
- `bairro` — texto — bairro da UC
- `classe` — texto — classe da UC
- `assunto` — texto
- `subassunto` — texto
- `data_hora_abertura` — data e hora (`yyyy-MM-dd HH:mm:ss`)
- `data_hora_fechamento` — data e hora (`yyyy-MM-dd HH:mm:ss`)
- `mes_referencia` — texto — `yyyy-MM`
- `aberto` — booleano
- `tempo_resolucao_horas` — decimal
- `qtd_tratativas` — inteiro
- `ultima_acao` — texto
- `nota_satisfacao` — decimal

`mes_referencia` é o mês da abertura. A situação vem de `aberto`, não de
`ultima_acao`; neste snapshot todos estão fechados. Médias de satisfação ignoram notas nulas.

---

# 8. `fila_inspecao`

## Grão

1 linha = 1 UC no snapshot da fila.

## Uso e limites

Priorizar suspeitas de perdas e estimar recuperação mensal. É um snapshot da Gold,
não histórico operacional completo nem ordens criadas no portal. Use `data_referencia_score`
(neste snapshot, `2026-06-30`) e `versao_regra_score` para situar a análise.
Score não é necessariamente probabilidade calibrada; estimativa de recuperação não significa perda confirmada
nem energia efetivamente recuperada. Não invente taxa geral de perdas a partir da fila.

## Colunas

- `id_uc` — texto — UC suspeita
- `prioridade` — inteiro — posição, 1 = mais prioritária
- `score` — decimal — pontuação de suspeita, de 0 a 100
- `motivo` — texto — justificativa da suspeita
- `kwh_estimado_recuperar_mes` — decimal — estimativa de kWh/mês, não perda medida
- `queda_consumo_pct` — decimal — queda em relação ao histórico da própria UC
- `consumo_vs_pares_pct` — decimal — negativo quando abaixo dos pares da mesma classe/município/bairro
- `tipo_medidor` — texto
- `idade_medidor_anos` — decimal
- `possui_gd` — booleano
- `queda_explicada_por_gd` — booleano — sinal usado na priorização
- `energia_injetada_atipica` — booleano
- `qtd_inspecoes_anteriores` — inteiro — histórico resumido da Silver, sem inspeções registradas no portal
- `resultado_ultima_inspecao` — texto — `IRREGULARIDADE CONFIRMADA`, `SEM IRREGULARIDADE` ou nulo
- `data_ultima_inspecao` — data — nula se nunca inspecionada
- `municipio` — texto
- `bairro` — texto
- `classe` — texto
- `data_referencia_score` — data — referência do snapshot
- `versao_regra_score` — texto

---

# 9. `fato_troca_medidor`

## Grão

1 linha = 1 troca de medidor.

## Uso e limites

Histórico de substituição e comparação de consumo antes/depois. Neste snapshot há
uma troca por UC, entre `2025-09` e `2026-03`; não assuma no máximo uma troca por UC em snapshots futuros.
Antes/depois não prova causalidade da troca: sazonalidade, GD e outros fatores podem afetar o consumo.
O mês da troca fica fora das duas médias; a janela posterior pode ter menos de seis meses.

## Colunas

- `id_uc` — texto
- `mes_troca` — texto — `yyyy-MM`
- `id_medidor_antigo` — texto
- `tipo_medidor_antigo` — texto
- `idade_medidor_antigo_anos` — decimal — idade na retirada
- `id_medidor_novo` — texto
- `tipo_medidor_novo` — texto
- `consumo_medio_6m_antes` — decimal — média mensal em kWh dos até seis meses anteriores
- `consumo_medio_6m_depois` — decimal — média mensal em kWh dos até seis meses seguintes
- `variacao_consumo_pct` — decimal — `(depois / antes - 1) * 100`, não efeito causal
- `classe` — texto
- `municipio` — texto
- `bairro` — texto

---

# Relacionamentos disponíveis

`dim_uc → fatos` por `id_uc` é 1:N: consumo mensal, interrupções, atendimentos e trocas.
Cadastro → fila é 1:0..1 por snapshot. Não autorize JOIN apenas por nomes semelhantes.
Consumo com interrupções ou atendimentos NÃO é 1:1: mesmo `id_uc + mês` pode ter
múltiplas ocorrências ou protocolos. Quando precisar combinar fatos, pré-agregue cada lado
no grão de ligação ou use `EXISTS` para filtrar sem multiplicar linhas.
Não some indicadores agregados depois de JOIN com fatos detalhados, nem medidas do cadastro
repetidas pelo JOIN. Relacionar indicadores de alimentador a detalhe exige alimentador/mês,
não apenas alimentador, e não torna suas medidas aditivas nas linhas detalhadas.

Não invente relacionamento entre tabelas agregadas quando o contrato não fornecer uma chave adequada.

Para análises já agregadas por município, bairro e classe, prefira utilizar diretamente `receita_decomposicao` em vez de reconstruir desnecessariamente a mesma agregação.

---

# Limitações conhecidas deste contrato

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

Receita do diagnóstico é `valor_energia`/`receita_energia` (sem tributos, bandeira embutida).
Faturamento com tributos usa `valor_total`/`receita_total`; nenhum deles significa automaticamente
arrecadação/caixa. Se a pergunta exigir outra definição financeira ou temporal não resolvida,
utilize `NEEDS_CLARIFICATION`, sem pedir esclarecimento sobre a definição já fixada do diagnóstico.

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
