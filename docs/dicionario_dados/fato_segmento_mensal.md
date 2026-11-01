# Dicionário de dados · `gold.fato_segmento_mensal`

> Contrato: tabela **A3** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fato_segmento_mensal.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

Pedido de Dev: a `kpis_mensal` tem uma linha por mês e não filtra por município, bairro ou classe, e a `receita_decomposicao` só compara os dois períodos fixos do diagnóstico. Esta tabela agrega consumo, receita e faturas por segmento e mês: o dashboard filtra direto nela, e a API calcula a decomposição preço × volume para qualquer par de períodos. Responde ao Henrique: "Qual bairro mais perdeu volume residencial no último ano?" e "Quanto a receita comercial cresceu em Jaboatão?".

**Quem usa:** dashboard executivo (com filtros), tela de receita (períodos livres e drill-down), insights de IA e agente.

**Grão:** 1 linha = 1 mês × 1 município × 1 bairro × 1 classe. Nesta base, os 1.106 segmentos existem nos 48 meses (todos têm UC ligada e fatura em todos os meses), então a tabela é uma grade completa.

**Linhas:** 53.088 (1.106 segmentos × 48 meses). **Validação do próprio notebook:** 47 checagens, todas `PASS`.

**Fontes (Gold):** `fato_consumo_faturamento` e `dim_uc`.

## Colunas (16)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

**Todas as colunas de valor são aditivas:** podem ser somadas entre segmentos e entre meses.

| Coluna | Tipo | Definição |
|---|---|---|
| `mes_referencia` | texto | `yyyy-MM` (competência) |
| `municipio` | texto | município |
| `bairro` | texto | bairro (usar sempre junto com `municipio`) |
| `classe` | texto | classe |
| `qtd_ucs_cadastradas` | inteiro | UCs do segmento ligadas até o fim do mês |
| `qtd_ucs_faturadas` | inteiro | UCs do segmento com fatura no mês |
| `qtd_ucs_com_gd` | inteiro | UCs do segmento com GD conectada até o mês (regra "GD no mês": inclui o mês da conexão) |
| `consumo_kwh` | decimal | energia faturada |
| `consumo_kwh_ucs_com_gd` | decimal | parte do consumo vinda de UCs com GD conectada no mês |
| `receita_energia` | decimal | soma de `valor_energia` (sem tributos; é a receita do diagnóstico) |
| `receita_total` | decimal | soma de `valor_total` (com tributos) |
| `qtd_faturas` | inteiro | faturas do mês (= `qtd_ucs_faturadas`: uma por UC e mês) |
| `qtd_faturas_em_aberto` | inteiro | faturas desta competência ainda em aberto |
| `valor_em_aberto` | decimal | `valor_total` das faturas desta competência em aberto |
| `qtd_faturas_bandeira_nao_verde` | inteiro | faturas com bandeira diferente de verde |
| `qtd_trocas_medidor` | inteiro | trocas de medidor no mês (6.299 no total, de `2025-09` a `2026-03`) |

## Decisões que afetam esta tabela

| Item | O que foi feito, e o efeito aqui |
|---|---|
| F2, L2 | Faturas e leituras órfãs removidas nas Silvers: a receita é ~1,5% menor que a da Bronze, e o consumo, ~0,4% |
| L5 | Troca de medidor: o consumo do mês da troca é a leitura atual do medidor novo; `qtd_trocas_medidor` marca esses meses |
| F5 | Faturas em aberto como flag (`em_aberto`); base de `qtd_faturas_em_aberto` e `valor_em_aberto` |
| Contrato | Só somas e contagens, **sem preço nem percentual**: assim todo recorte pode ser somado sem erro |
| Contrato | Segmento com UC ligada e sem fatura no mês entraria com as somas em zero (não acontece nesta base) |

## Cuidados de uso

- **Preços e percentuais se calculam depois de somar.** Preço médio = `soma(receita_energia) ÷ soma(consumo_kwh)`; inadimplência = `soma(valor_em_aberto) ÷ soma(receita_total)`; % de bandeira não verde = `soma(qtd_faturas_bandeira_nao_verde) ÷ soma(qtd_faturas)`. Nunca fazer a média dos valores de cada linha.
- **Decomposição preço × volume para dois períodos quaisquer (regra para a API):** somar `consumo_kwh` (V) e `receita_energia` (R) de cada período, com o filtro desejado, e aplicar `efeito_volume = (V1 − V0) × R0/V0` e `efeito_preco = (R1 − R0) − efeito_volume`. Se o volume de um período for zero, toda a variação é efeito-volume. **Nunca somar efeitos calculados por segmento** (efeito composição; ver a `receita_decomposicao`). A função `decompor` do notebook (seção 9) é a referência.
- **Contagens de UCs não se somam entre meses:** `qtd_ucs_cadastradas`, `qtd_ucs_faturadas` e `qtd_ucs_com_gd` somam entre segmentos do mesmo mês, mas, para um período, usar o valor do último mês (ou a média), e não a soma dos meses.
- **"No último ano" e "desde o primeiro ano" dão respostas diferentes.** A `receita_decomposicao` compara os últimos 12 meses com o primeiro ano; esta tabela permite qualquer par. O agente deve dizer qual período usou.
- **A pergunta pode trazer uma premissa errada:** a receita comercial de Jaboatão **caiu** (−5,1% no último ano contra o anterior; −2,1% contra o primeiro ano). O agente deve corrigir a premissa, e não responder "cresceu".
- **Bairro só vale junto com o município** (297 pares, 272 nomes de bairro).
- **Os meses atípicos** (`2025-07`, `2025-11` e `2026-02`) e a inadimplência por competência seguem os cuidados da `kpis_mensal`.

## Como foi validada

- Chave `(mes_referencia, municipio, bairro, classe)` única; 48 meses; 297 pares município + bairro; 1.106 segmentos em todos os meses.
- Todas as somas iguais às da `fato_consumo_faturamento`: consumo, consumo com GD, receitas, faturas, em aberto, valor em aberto, não verdes, trocas e UCs com GD.
- Volume e receita dos dois períodos iguais ao diagnóstico; 45.000 UCs e 3.510 com GD em `2026-06`; 6.299 trocas.
- **A soma dos segmentos de cada mês é igual à `kpis_mensal`** nas 7 colunas em comum, nos 48 meses.
- **Somando os dois períodos por segmento, volume e receita são iguais aos da `receita_decomposicao`** nas 1.106 linhas.
- A função de decomposição reproduz os efeitos do diagnóstico (−R$ 4.657.042 de volume e +R$ 14.089.243 de preço).
