# Dicionário de dados · `gold.kpis_mensal`

> Contrato: tabela **A5** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_kpis_mensal.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

User story do diretor: "ver os principais indicadores do negócio e compará-los entre períodos, para saber rapidamente se estamos indo bem ou mal". É o resumo da empresa inteira; para recortes por município, bairro ou classe, o dashboard usa a A3.

**Quem usa:** dashboard executivo (cards e gráficos), agente de IA e diagnóstico.

**Grão:** 1 linha = 1 mês de referência (`2022-07` a `2026-06`).

**Linhas:** 48 (1 por mês, `2022-07` a `2026-06`). **Validação do próprio notebook:** 46 checagens, todas `PASS`.

## Colunas (20)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `mes_referencia` | texto | `yyyy-MM` |
| `qtd_ucs_cadastradas` | inteiro | UCs ligadas até o fim do mês |
| `qtd_ucs_faturadas` | inteiro | UCs com fatura no mês |
| `consumo_total_kwh` | decimal | energia faturada no mês |
| `receita_energia` | decimal | soma de `valor_energia` |
| `receita_total` | decimal | soma de `valor_total` (com tributos) |
| `preco_medio_kwh` | decimal | `receita_energia / consumo_total_kwh` |
| `bandeira_predominante` | texto | bandeira com mais faturas no mês |
| `pct_faturas_bandeira_nao_verde` | decimal | % de faturas com bandeira diferente de verde |
| `qtd_faturas_em_aberto` | inteiro | faturas **desta competência** ainda em aberto |
| `inadimplencia_pct` | decimal | % do `valor_total` **desta competência** em aberto (não mistura dívida de meses anteriores) |
| `valor_em_aberto_mais_90_dias` | decimal | valor desta competência em aberto há mais de 90 dias |
| `qtd_ucs_com_gd` | inteiro | UCs com GD conectada até o mês (regra "GD no mês"; igual à soma da A3 no mês) |
| `qtd_interrupcoes` | inteiro | ocorrências no mês |
| `dec_horas` | decimal | DEC geral do mês (`minutos / 60 / qtd_ucs_cadastradas`) |
| `fec` | decimal | FEC geral do mês (`ocorrências / qtd_ucs_cadastradas`) |
| `qtd_atendimentos` | inteiro | chamados abertos no mês. **`2025-07` tem 18.061, cerca de 2,8× o normal** (evento climático; log A6) |
| `nota_satisfacao_media` | decimal | média das notas do mês, **só das preenchidas**, na escala de 1 a 5 (os chamados sem avaliação não entram) |
| `variacao_consumo_ano_anterior_pct` | decimal | consumo vs mesmo mês do ano anterior (nula de `2022-07` a `2023-06`) |
| `variacao_receita_ano_anterior_pct` | decimal | receita vs mesmo mês do ano anterior (nula de `2022-07` a `2023-06`) |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| F2 e L2 | Faturas e leituras órfãs removidas | consumo e receita mensais são ~1,5% menores que os da Bronze |
| L5 | Troca de medidor: consumo = `leitura_atual` | entra no consumo mensal dos meses de troca (2025-09 a 2026-03) |
| F5 | Fatura sem pagamento: nulo real e `em_aberto` | base de `qtd_faturas_em_aberto`, `inadimplencia_pct` e `valor_em_aberto_mais_90_dias` |
| A6 | Pico de julho de 2025 mantido | `qtd_atendimentos` de 2025-07 é 18.061 |
| O1 a O3 | Ocorrências de rede: causa ausente em 4 formas, duração com o sufixo ` min`, datas como texto | tratadas na Silver; `qtd_interrupcoes`, `dec_horas` e `fec` vêm da `fato_interrupcao` (180.000 ocorrências) |

## Cuidados de uso

- **A inadimplência é por competência, e a conta depende do que se mede:** em cada mês, de **7,8% a 8,2% das faturas** ficam em aberto (`qtd_faturas_em_aberto`), mas isso é de **5% a 6% do valor** (`inadimplencia_pct`), porque as faturas em aberto têm valor menor que a média. Não use `dias_atraso` das pagas como inadimplência (83% têm algum atraso).
- **`valor_em_aberto_mais_90_dias` é zero de `2026-04` a `2026-06`** e parcial em `2026-03`, por construção: o atraso das faturas em aberto é contado até 2026-06-30, e as faturas desses meses ainda não passaram de 90 dias.
- **`qtd_atendimentos` conta os chamados com abertura no mês**; `2025-07` tem 18.061, ~2,8× o normal. Não há chamados em aberto.
- **Os três meses fora do padrão:** `2025-07` tem 17.844 interrupções (5,3× o normal de ~3,4 mil; `dec_horas` de 1,94 contra ~0,125 e `fec` de 0,40 contra ~0,075) e 18.061 chamados com nota 3,11; `2025-11` e `2026-02` têm 1,6× as interrupções e consumo cerca de 8% acima do ano anterior, contra −1% a −4% nos outros meses.
- **`dec_horas` e `fec` usam como denominador as UCs cadastradas do próprio mês**, e não as do alimentador (essa é a `dec_fec_alimentador_mensal`).
- **A UC é faturada a partir do mês seguinte ao da ligação:** `qtd_ucs_faturadas` de um mês é igual à `qtd_ucs_cadastradas` do mês anterior em todos os 47 meses comparáveis. Por isso as duas colunas diferem de poucas UCs.
- **Os preços dos períodos** devem ser calculados como `receita ÷ volume` (somando antes de dividir), e não como a média dos preços mensais. O preço médio sobe em degraus em maio de cada ano (+7,4% em `2023-05` e +3,0% em `2024-05`), compatíveis com reajustes de tarifa (não verificado contra a regulação), e varia com a bandeira.
- **Bandeira:** todas as faturas de um mês têm a mesma bandeira (`pct_faturas_bandeira_nao_verde` é 0 ou 100 nos 48 meses), então `bandeira_predominante` é a bandeira do mês. Nos últimos 12 meses são 8 meses não verdes (3 vermelha P1, 2 vermelha P2 e 3 amarela) e 4 verdes.
- **`nota_satisfacao_media`** usa só as notas preenchidas (os 3,0% sem avaliação não entram).
- As variações contra o ano anterior são nulas de `2022-07` a `2023-06`; a do consumo fica perto de −3% desde `2024-11`, exceto em `2025-11` e `2026-02` (+8,5% e +8,0%).

## Como foi validada

- A soma do consumo e da receita dos 48 meses é igual à da `fato_consumo_faturamento` (891.449.321 kWh e R$ 499.862.082,73).
- Volume e receita de energia dos dois períodos iguais ao diagnóstico (227.052.927 e 218.079.054 kWh; R$ 117.830.394,38 e R$ 127.262.595,65).
- 172.553 faturas em aberto, 318.871 chamados (18.061 em 2025-07) e 180.000 interrupções (17.844 em 2025-07).
- 3.510 UCs com GD e 45.000 UCs cadastradas em `2026-06`; as duas contagens nunca diminuem de um mês para o seguinte.
- As horas interrompidas somam 356.534,8 (`duracao_min` ÷ 60), o valor que a `fato_interrupcao` declara (356.535).
