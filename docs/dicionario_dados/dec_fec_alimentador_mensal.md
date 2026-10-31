# Dicionário de dados · `gold.dec_fec_alimentador_mensal`

> Contrato: tabela **A8** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_dec_fec_alimentador_mensal.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

A Beatriz: "a ANEEL cobra DEC e FEC da gente [...] quero acompanhar esses indicadores por alimentador, saber quais regiões concentram as piores interrupções e onde a manutenção preventiva dá mais retorno". Requisito 5.1: calcular DEC e FEC por alimentador.

**Quem usa:** tela de qualidade do serviço (cards, evolução e ranking) e agente de IA.

**Grão:** 1 linha = 1 alimentador × 1 mês, com **grade completa**: 122 alimentadores × 48 meses (`2022-07` a `2026-06`). Mês sem interrupção aparece com DEC e FEC **zero**.

**Linhas:** 5.856. **Validação do próprio notebook:** 38 checagens, todas `PASS`.

**Fontes (Gold):** `fato_interrupcao` e `dim_uc`.

## Colunas (14)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `alimentador` | texto | código do alimentador (`ALM-XXX-000`; as 3 letras do meio indicam o município) |
| `municipio` | texto | município do alimentador (cada alimentador atende um único município) |
| `mes_referencia` | texto | `yyyy-MM` |
| `qtd_ucs_alimentador_mes` | inteiro | UCs do alimentador com `data_ligacao` até o último dia do mês (denominador). De 20 a 2.285 UCs; mediana de 295 |
| `qtd_interrupcoes` | inteiro | ocorrências no mês (cada uma é 1 UC interrompida) |
| `horas_interrompidas` | decimal | soma das durações, em horas. Como cada ocorrência é uma UC, é o total de **UC × horas sem luz**: a medida de impacto |
| `qtd_interrupcoes_evitaveis` | inteiro | ocorrências com `causa_evitavel = true` (vegetação, falha de equipamento e sobrecarga) |
| `horas_causas_evitaveis` | decimal | horas dessas ocorrências (o que a manutenção preventiva poderia reduzir); **é um piso**, porque a causa nula conta como não evitável |
| `dec_horas` | decimal | `horas_interrompidas ÷ qtd_ucs_alimentador_mes`: horas sem luz por UC no mês |
| `fec` | decimal | `qtd_interrupcoes ÷ qtd_ucs_alimentador_mes`: interrupções por UC no mês |
| `dec_12m_horas` | decimal | soma do `dec_horas` dos 12 meses até este mês (o mês e os 11 anteriores). **Nula de `2022-07` a `2023-05`** |
| `fec_12m` | decimal | soma do `fec` dos 12 meses até este mês. **Nula de `2022-07` a `2023-05`** |
| `causa_principal` | texto | causa **informada** com mais horas no mês (empate: a de nome menor). Nula em mês sem interrupção |
| `ranking_dec_mes` | inteiro | posição do alimentador no mês por `dec_horas` (1 = pior); empate decidido pelas horas interrompidas e pelo código. Posições de 1 a 122, sem repetição |

## Decisões que afetam esta tabela

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| O1 | Causa ausente em 5.400 ocorrências | entram nas horas, no DEC e no FEC; não disputam a `causa_principal` e contam como não evitáveis |
| O2 | Duração com o sufixo ` min` (16.200) | convertida na Silver; sem isso, o DEC sairia ~9% menor |
| X1 | 584 ocorrências (218 UCs) em meses anteriores à ligação da UC | mantidas: entram no numerador, mas a UC ainda não está no denominador. Cerca de 0,3% das ocorrências; no alimentador mais afetado (`ALM-JAB-015`, 44 ocorrências em 1 UC), ~2% das ocorrências |
| Contrato | `dec_12m_horas` e `fec_12m` nulos antes de `2023-06` | a base começa em `2022-07`; um acumulado de menos de 12 meses ficaria menor que o real e distorceria o ranking |
| Contrato | `OSCILACAO` entra no DEC e no FEC | o glossário diz que cada registro é uma UC interrompida (suposição registrada no README) |

## Cuidados de uso

- **O DEC de alimentador pequeno é alto com poucas ocorrências.** As horas sem luz por ano ficam numa faixa estreita (cerca de 670 a 930 horas nos alimentadores das listas do notebook, tirando os três do evento de julho de 2025), qualquer que seja o tamanho. Por isso o ranking de DEC é dominado pelos menores: os sete piores de 12 meses têm de 20 a 47 UCs. **Mostrar sempre o DEC junto com `qtd_ucs_alimentador_mes` e `horas_interrompidas`**, para a priorização não ir só para onde afeta pouca gente.
- **`ALM-JAB-016` (20 UCs) é o pior DEC em quase todos os meses desde 2022:** 43,9 horas e 19,6 interrupções por UC nos últimos 12 meses, contra ~3,4 horas e ~1,3 interrupções na média da empresa em 2025.
- **Em impacto (`horas_interrompidas`), os piores são os três do evento de julho de 2025:** `ALM-REC-008` (34.405 h nos últimos 12 meses), `ALM-SAO-004` (16.985 h) e `ALM-JAB-004` (13.244 h), com só 1% a 2% de horas evitáveis. Nos demais, 25% a 47% das horas são evitáveis.
- **Para a manutenção preventiva, ordenar por `horas_causas_evitaveis`:** nos últimos 12 meses, `ALM-CAB-006` (385 h), `ALM-REC-018` (364 h) e `ALM-ABR-002` (337 h) lideram.
- **DEC e FEC de um conjunto (município ou empresa) não são a média dos alimentadores:** some `horas_interrompidas` e `qtd_interrupcoes` e divida pela soma de `qtd_ucs_alimentador_mes`. Feito assim, o DEC da empresa é de 1,50 h em 2023 e 2024 e de 3,39 h em 2025 (o evento de julho); o FEC, de 0,90 e 1,27.
- **`dec_12m_horas` é a soma dos DECs mensais**, como a apuração anual. Ele carrega um mês ruim por 12 meses: o evento de julho de 2025 pesa no acumulado até `2026-06`.
- **`causa_principal` é a do mês, e não a do ano.** Nos últimos 12 meses, a climática é a mais frequente (352 alimentador-meses), seguida de sobrecarga (248).
- **2022 e 2026 têm seis meses cada.** Comparar anos completos ou usar o acumulado de 12 meses.
- **Não atribuir o DEC do alimentador a cada bairro:** a análise por bairro usa a `fato_interrupcao`, com as UCs do bairro como denominador.

## Como foi validada

- 5.856 linhas, sem par alimentador × mês repetido; 122 alimentadores e 48 meses; um município por alimentador.
- Nenhum alimentador com zero UCs; o denominador nunca diminui; 45.000 UCs somadas em `2026-06`.
- A soma das ocorrências (180.000), dos minutos e das ocorrências e minutos evitáveis é igual à da `fato_interrupcao`.
- `dec_horas` e `fec` conferidos linha a linha contra as fórmulas; zero nos meses sem interrupção.
- Acumulado de 12 meses nulo antes de `2023-06` e preenchido depois; ranking de 1 a 122 em cada mês, com o 1º lugar no maior DEC.
- 17.844 ocorrências em `2025-07`, com `ALM-REC-008`, `ALM-SAO-004` e `ALM-JAB-004` como os três com mais ocorrências.
