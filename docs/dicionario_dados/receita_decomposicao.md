# Dicionário de dados · `gold.receita_decomposicao`

> Contrato: tabela **A4** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_receita_decomposicao.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

Responde à pergunta central do case. O Henrique: "quero ver por bairro e por classe, e quero saber quanto da variação foi preço e quanto foi quantidade de energia. Se foi volume, quero saber onde e por quê." É a versão **fixa e auditada** dos dois períodos do diagnóstico; para outros períodos, a tela usa a A3.

**Quem usa:** tela de receita (drill-down e waterfall), diagnóstico, insights e agente de IA.

**Grão:** 1 linha = 1 combinação município × bairro × classe, comparando o primeiro ano (0) com os últimos 12 meses (1).

**Linhas:** 1.106 (município × bairro × classe). **Validação do próprio notebook:** 35 checagens, todas `PASS`.

## Colunas (24)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `municipio` | texto | município |
| `bairro` | texto | bairro |
| `classe` | texto | classe |
| `qtd_ucs_periodo_0` | inteiro | UCs com fatura no primeiro ano |
| `qtd_ucs_periodo_1` | inteiro | UCs com fatura nos últimos 12 meses |
| `volume_kwh_0` | decimal | energia faturada no primeiro ano |
| `volume_kwh_1` | decimal | energia faturada nos últimos 12 meses |
| `receita_0` | decimal | soma de `valor_energia` no primeiro ano |
| `receita_1` | decimal | soma de `valor_energia` nos últimos 12 meses |
| `preco_medio_0` | decimal | `receita_0 / volume_kwh_0` |
| `preco_medio_1` | decimal | `receita_1 / volume_kwh_1` |
| `variacao_receita` | decimal | `receita_1 − receita_0` |
| `variacao_receita_pct` | decimal | variação em % |
| `variacao_volume_pct` | decimal | variação do volume em % |
| `efeito_preco` | decimal | parte da variação explicada pelo preço (reajuste + bandeira) |
| `efeito_volume` | decimal | parte da variação explicada pelo volume |
| `consumo_medio_uc_0` | decimal | `volume_kwh_0 / qtd_ucs_periodo_0` |
| `consumo_medio_uc_1` | decimal | `volume_kwh_1 / qtd_ucs_periodo_1` |
| `qtd_ucs_com_gd_1` | inteiro | UCs com GD conectada até o fim do período 1 (regra "GD no mês" aplicada a `2026-06`) |
| `volume_kwh_ucs_com_gd_0` | decimal | volume, no período 0, das UCs que têm GD no fim do período 1 |
| `volume_kwh_ucs_com_gd_1` | decimal | volume dessas mesmas UCs no período 1 (a diferença é a queda explicada pela GD) |
| `qtd_trocas_medidor_1` | inteiro | trocas de medidor no período 1 |
| `pct_faturas_bandeira_nao_verde_0` | decimal | % de faturas não verdes no primeiro ano (0% nos dados) |
| `pct_faturas_bandeira_nao_verde_1` | decimal | idem nos últimos 12 meses (~67% nos dados) |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| F2 e L2 | Faturas e leituras órfãs removidas na Silver | a receita e o volume desta tabela são ~1,5% menores que os da Bronze (a variação de receita seria +7,90% com as faturas órfãs, em vez de +8,00%) |
| L5 | Troca de medidor: consumo = `leitura_atual` (6.299) | única regra que reproduz o −3,95% de volume; `qtd_trocas_medidor_1` conta esses meses |
| L4 | Consumo com sinal invertido corrigido (1.717) | sem a correção, o volume sairia subestimado |
| — | Receita = `valor_energia` (sem tributos) | decisão do contrato; a variação é a mesma com `valor_total` |

## Cuidados de uso

- **`efeito_preco` e `efeito_volume` NÃO são aditivos entre linhas.** Cada linha usa o preço do próprio segmento, e o preço médio de um conjunto mistura os preços dos segmentos (efeito composição). Para qualquer nível acima da linha (município, classe, empresa), **some `volume_kwh_*` e `receita_*` e aplique as fórmulas de novo**. Medido na própria tabela, o efeito-volume soma −R$ 4.657.042 na empresa, −R$ 4.994.045 por classe, −R$ 4.662.467 por município e −R$ 4.993.510 por linha; a diferença de ≈ R$ 337 mil vem das classes.
- **`consumo_medio_uc_0` e `_1` são o consumo por UC nos 12 meses do período**, e não por mês (dividir por 12 dá uma aproximação, com erro de ~0,1% na empresa).
- **`efeito_preco` mistura tarifa e bandeira:** o adicional da bandeira não vem separado na fatura. Estimativa do diagnóstico: no residencial, o preço subiu 13,0%, contra 10,5% de reajuste, o que deixa ≈ 2,3% (1,130 ÷ 1,105 − 1) para a bandeira.
- **`qtd_ucs_com_gd_1`** conta as UCs com GD conectada até o fim do período 1 (3.510); `volume_kwh_ucs_com_gd_0` e `_1` mostram a queda associada à GD (−61%). É associação, e não causa comprovada.
- **A comparação é com o primeiro ano** (`2022-07` a `2023-06`). A pergunta "no último ano" (contra 2024-07 a 2025-06) exige a `fato_segmento_mensal`.
- **`pct_faturas_bandeira_nao_verde_1`** é 66,67% nos exemplos observados (8 meses não verdes em 12); no primeiro ano é 0%.

## Como foi validada

- Volume, receita e UCs dos dois períodos iguais ao diagnóstico; efeito-volume global de −R$ 4.657.042 e efeito-preço de +R$ 14.089.243 (variação de +R$ 9.432.201).
- `efeito_volume + efeito_preco = variacao_receita` em todas as linhas (até 1 centavo).
- 3.510 UCs com GD e 6.299 trocas de medidor.
- 0 segmentos sem correspondência na `dim_uc`.
