# Dicionário de dados · `gold.fato_interrupcao`

> Contrato: tabela **A7** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fato_interrupcao.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

A Camila quer saber "se a rua dele teve falta de luz" na visão 360. A Beatriz quer "saber quais regiões concentram as piores interrupções e onde a manutenção preventiva dá mais retorno". É também a base da `dec_fec_alimentador_mensal` (A8) e das respostas do agente sobre "falta de luz".

**Quem usa:** visão 360 (a UC ficou sem luz?), tela de qualidade do serviço (análise por causa e local), `dec_fec_alimentador_mensal` e agente de IA.

**Grão:** 1 linha = 1 ocorrência de interrupção em 1 UC. O glossário do case diz que cada registro é uma UC interrompida, então uma queda que atinge 100 UCs aparece em 100 linhas.

**Linhas:** 180.000 (1 por ocorrência). **Validação do próprio notebook:** 32 checagens, todas `PASS`.

**Fontes (Silver):** `ocorrencias_rede` e `unidades_consumidoras`.

## Colunas (13)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `id_ocorrencia` | texto | identificador da ocorrência |
| `id_uc` | texto | UC interrompida |
| `alimentador` | texto | alimentador da ocorrência (`ALM-XXX-000`); **sempre igual ao do cadastro da UC** |
| `municipio` | texto | município da UC |
| `bairro` | texto | bairro da UC (usar sempre junto com `municipio`) |
| `classe` | texto | classe da UC |
| `tipo` | texto | `FALTA DE ENERGIA`, `DANO EM EQUIPAMENTO`, `OSCILACAO`, `SOBRECARGA` ou `FIO PARTIDO` |
| `causa` | texto | `CLIMATICA`, `SOBRECARGA`, `NAO IDENTIFICADA`, `VEGETACAO`, `TERCEIROS` ou `FALHA DE EQUIPAMENTO`; **nula em 5.400 ocorrências sem causa informada** (log O1). `NAO IDENTIFICADA` é uma causa registrada, e não ausência |
| `causa_evitavel` | booleano | `true` para `VEGETACAO`, `FALHA DE EQUIPAMENTO` e `SOBRECARGA` (evitáveis com manutenção preventiva); `false` para as demais **e para a causa nula**. Nunca nula |
| `data_hora_inicio` | data e hora | abertura da ocorrência (**com horário**) |
| `data_hora_fim` | data e hora | encerramento (**com horário**; nenhuma ocorrência em aberto nesta base) |
| `mes_referencia` | texto | `yyyy-MM` do início (de `2022-07` a `2026-06`) |
| `duracao_min` | inteiro | duração em minutos; igual a `fim − início` em 100% das linhas (de 5 minutos a 48 horas; mediana de 72 min) |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| O1 | `causa` ausente em 4 formas: nulo, `-`, `N/A` e `NULL` (5.400; 3,0%) | vira nulo real; a ocorrência é mantida e entra no DEC/FEC. Aqui, `causa_evitavel = false` |
| O2 | `duracao_min` com o texto ` min` (16.200; 9,0%) | sufixo removido e convertido para inteiro. Sem isso, 9% das durações seriam nulas e o DEC sairia subestimado |
| O3 | Datas como texto | convertidas para data e hora, mantendo o horário; `mes_referencia` derivado da abertura |
| U5, U6 | Município e bairro com grafias diferentes e acentuação corrompida | padronizados na Silver de UCs; o bairro vale junto com o município (297 pares) |

A Silver não remove nenhuma ocorrência: não há cópias, registros em dobro (mesma UC e mesma abertura), órfãs nem UCs de teste.

## Cuidados de uso

- **Esta tabela diz se a própria UC ficou sem luz**, e não a rua. Para "a rua dele teve falta de luz", o backend busca as ocorrências do mesmo alimentador ou do mesmo logradouro e bairro no período.
- **Cada linha é uma UC interrompida**, e não um evento de rede. Somar `duracao_min` dá **UC × minutos sem luz** (a medida de impacto), e não a duração de um evento.
- **`causa_evitavel` é um piso:** as 5.400 ocorrências sem causa ficam como não evitáveis. Nesta base, as causas evitáveis somam **130.743 horas (36,7%)** das 356.535 horas interrompidas.
- **`OSCILACAO` entra** (14.562 ocorrências; 23.834 h), porque o glossário diz que cada registro é uma UC interrompida. É uma suposição registrada no README; quem quiser excluir filtra por `tipo`.
- **Julho de 2025 é um evento:** 17.844 ocorrências (5,3× o normal), 97% climáticas e 72% em três alimentadores (`ALM-REC-008`, `ALM-SAO-004` e `ALM-JAB-004`). Ele dobra as horas de 2025 (152.549, contra ~67 mil em 2023 e 2024) e faz **São Lourenço da Mata** ter 18,4 horas por UC, contra 6 a 9 h nos outros municípios, com só 16% evitáveis.
- **A causa climática dura mais:** mediana de 101 min, contra 65 a 67 min nas demais causas.
- **2022 tem só seis meses** (a base começa em `2022-07`). Comparar anos completos ou períodos de 12 meses.
- **Para comparar regiões, dividir pelas UCs da região.** Somar horas por município ou bairro favorece as regiões maiores. Bairros pequenos dão valores instáveis; as consultas do notebook usam no mínimo 50 UCs.
- **Não atribuir o DEC do alimentador a cada bairro:** a análise por bairro usa esta tabela, com as UCs do bairro como denominador.
- **Horários locais, sem fuso:** o `Z` que o Databricks exibe é só a exibição; não converter fuso.

## Como foi validada

- 180.000 linhas, igual à `silver.ocorrencias_rede`; `id_ocorrencia` único; soma de `duracao_min` idêntica à da Silver.
- `fim − início = duracao_min` em 100% das linhas (tolerância de 1 minuto); nenhum fim antes do início.
- 5.400 causas nulas, `causa_evitavel` coerente com a causa em todas as linhas, 122 alimentadores e 17.844 ocorrências em 2025-07.
- Alimentador da ocorrência igual ao do cadastro em 100% das linhas.
- 0 UCs fora da `dim_uc` e 0 com município, bairro, classe ou alimentador diferentes. 41.512 das 45.000 UCs tiveram ao menos uma interrupção.
