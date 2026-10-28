# Dicionário de dados · `gold.fato_consumo_faturamento`

> Contrato: tabela **A2** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fato_consumo_faturamento.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

Une medição e faturamento, que hoje vivem em sistemas separados. Responde ao "consumo dos últimos meses ao lado do mesmo período do ano passado" e às "faturas em aberto" da Camila (inclusive "quando ele reclama de conta alta"), e é a base das contas de volume e receita do Henrique.

**Quem usa:** visão 360 (consumo contra o mesmo mês do ano anterior e faturas), diagnóstico da receita e agente de IA.

**Grão:** 1 linha = 1 UC em 1 mês de referência (1 leitura + 1 fatura; as Silvers garantem exatamente uma de cada: 2.152.336 pares).

**Linhas:** 2.152.336 (1 por UC e mês). **Validação do próprio notebook:** 52 checagens, todas `PASS`.

## Colunas (31)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `id_uc` | texto | UC |
| `mes_referencia` | texto | competência `yyyy-MM` |
| `ano` | inteiro | ano da competência |
| `mes` | inteiro | mês da competência (1 a 12) |
| `periodo_diagnostico` | texto | `PRIMEIRO_ANO` (`2022-07` a `2023-06`), `ULTIMOS_12M` (`2025-07` a `2026-06`) ou `OUTRO` |
| `classe` | texto | classe da UC (repetida para facilitar consultas do agente) |
| `bairro` | texto | bairro da UC |
| `municipio` | texto | município da UC |
| `possui_gd_no_mes` | booleano | UC já tinha GD conectada neste mês (regra "GD no mês" das convenções: inclui o mês da conexão) |
| `id_medidor` | texto | medidor que fez a leitura |
| `data_leitura` | data | data da leitura |
| `tipo_leitura` | texto | `REAL` ou `ESTIMADA` |
| `consumo_kwh` | inteiro | consumo do mês, já tratado (L4, L5). **No mês de troca de medidor, é a leitura atual do medidor novo**: essa regra reproduz o −4% do diretor |
| `consumo_kwh_ano_anterior` | inteiro | mesma UC, mesmo mês do ano anterior (nulo se não houver) |
| `variacao_consumo_ano_anterior_pct` | decimal | variação em % sobre o ano anterior. **Nula em todo o primeiro ano** (`2022-07` a `2023-06`) e nos meses de UCs que ainda não existiam um ano antes |
| `troca_medidor` | booleano | mês da troca de medidor (L5) |
| `consumo_corrigido` | booleano | consumo com sinal corrigido (L4) |
| `leitura_anterior_ausente` | booleano | leitura anterior faltante (L3) |
| `id_fatura` | texto | fatura do mês |
| `data_emissao` | data | emissão |
| `data_vencimento` | data | vencimento |
| `data_pagamento` | data | pagamento (nulo se em aberto) |
| `valor_energia` | decimal | valor da energia, sem tributos, **com o adicional de bandeira embutido** (é a receita do diagnóstico) |
| `tributos` | decimal | tributos |
| `valor_total` | decimal | total da fatura |
| `bandeira_tarifaria` | texto | `Verde`, `Amarela`, `Vermelha P1` ou `Vermelha P2` (só o nome; o valor do adicional não vem separado) |
| `status_fatura` | texto | `PAGA` ou `EM ABERTO` |
| `em_aberto` | booleano | fatura não paga |
| `dias_atraso` | inteiro | dias entre vencimento e pagamento (ou até 2026-06-30, se em aberto); 0 se pago em dia ou se ainda não venceu |
| `faixa_atraso` | texto | `EM DIA` (0), `ATE 30 DIAS` (1 a 30), `31 A 90 DIAS` (31 a 90) ou `MAIS DE 90 DIAS` (mais de 90) |
| `preco_medio_kwh` | decimal | `valor_energia / consumo_kwh` |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| L1 | Cópias exatas de leituras (21.523 linhas) | removidas na Silver; cada leitura aparece uma vez |
| L2 | Leituras órfãs, com `id_medidor` inexistente (8.609) | removidas na Silver (ficam na Bronze) |
| F1 | Linha de cabeçalho repetida como dado nas faturas (2) | removida na Silver |
| F2 | Faturas órfãs: UC inexistente no cadastro (32.285; R$ 7,64 mi de `valor_energia`, 1,5%) | removidas na Silver. **A receita desta tabela é ~1,5% menor que a da Bronze** |
| L3 | `leitura_anterior` ausente em 4 formas (32.285 linhas) | vira nulo real, com a flag `leitura_anterior_ausente`; o consumo é mantido |
| L4 | Consumo negativo por sinal invertido (1.717) | corrigido com valor absoluto; flag `consumo_corrigido` |
| L5 | Consumo negativo por troca de medidor, de 2025-09 a 2026-03 (6.299) | `consumo_kwh` passa a ser a `leitura_atual`; flag `troca_medidor`. É o que faz o volume reproduzir o −3,95% do diretor |
| L6 e F4 | Datas em 4 formatos de texto | convertidas para data (hífen = mês primeiro) |
| F3 | `valor_total` escrito como moeda, `R$ 1.234,56` (196.622) | normalizado para decimal; `valor_total = valor_energia + tributos` em 100% das linhas |
| F5 | `data_pagamento` ausente, como nulo e como `9999-12-31` (175.168 na Silver) | vira nulo real; flag `em_aberto`. Na Gold são 172.553 faturas em aberto |

## Cuidados de uso

- **Faturas em aberto:** são 172.553 (8% das faturas), em todos os anos desde 2022; 160.318 (93%) estão em `MAIS DE 90 DIAS`. A tela deve separar as recentes das antigas pela `faixa_atraso`.
- **`dias_atraso` não mede inadimplência:** 83% das faturas pagas têm algum atraso (média de 10,8 dias contando as pagas em dia; máximo de 25). A inadimplência é medida por competência: a % do valor em aberto de cada mês, sem misturar a dívida de meses anteriores.
- **`variacao_consumo_ano_anterior_pct` e `consumo_kwh_ano_anterior` são nulos em todo o primeiro ano** (`2022-07` a `2023-06`) e em poucas UCs que ainda não existiam um ano antes. O ano anterior é buscado pelo mesmo mês exato, e não por posição.
- **Troca de medidor:** nos 6.299 meses de troca, o consumo é a leitura atual e o `preco_medio_kwh` fica ~5% acima do típico.
- **`consumo_kwh` já vem líquido da geração distribuída** (cai ~69% depois da conexão). `possui_gd_no_mes` é verdadeiro **do mês da conexão em diante**, e o mês da conexão costuma cair só em parte.
- **`classe`, `bairro` e `municipio`** são copiados do cadastro para facilitar filtros; o bairro só vale junto com o município (297 pares, 272 nomes de bairro).
- **Receita:** use `valor_energia` (sem tributos); `valor_total` vem junto, e a variação é a mesma (+8,00%).

## Como foi validada

- A soma de `consumo_kwh` e de `valor_energia` é igual à das Silvers de leituras e faturas.
- O volume dos dois períodos do diagnóstico (227.052.927 e 218.079.054 kWh) e a receita de energia (R$ 117.830.394,38 e R$ 127.262.595,65) são reproduzidos ao centavo.
- O consumo do ano anterior coincide com um `lag(12)` independente em todas as 44.638 UCs com os 48 meses (0 divergências).
- 0 UCs da tabela fora da `dim_uc`.
