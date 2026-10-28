# Dicionário de dados · `gold.fila_inspecao`

> Contrato: tabela **B2** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fila_inspecao.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

O Rafael: "quero abrir o sistema e ver uma fila das unidades suspeitas, da mais promissora para a menos promissora, com o motivo da suspeita e quanta energia dá para recuperar em cada uma. [...] Uma lista com mil nomes sem ordem não me serve".

**Quem usa:** tela de perdas (fila e criação de ordens de inspeção) e agente de IA.

**Grão:** 1 linha = 1 UC suspeita.

**Linhas:** 906 (UCs suspeitas, regra v1). **Validação do próprio notebook:** 32 checagens, todas `PASS`.

## Colunas (20)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `id_uc` | texto | UC suspeita |
| `prioridade` | inteiro | posição na fila (1 = mais promissora) |
| `score` | decimal | pontuação de suspeita (0 a 100) |
| `motivo` | texto | motivo legível (ex.: "consumo caiu 60% vs. 12 meses anteriores; medidor eletromecânico com 22 anos") |
| `kwh_estimado_recuperar_mes` | decimal | consumo esperado − consumo atual, por mês (nunca negativo) |
| `queda_consumo_pct` | decimal | queda vs. histórico da própria UC |
| `consumo_vs_pares_pct` | decimal | consumo vs. UCs da mesma classe e do mesmo município + bairro |
| `tipo_medidor` | texto | tipo do medidor ativo |
| `idade_medidor_anos` | decimal | idade do medidor ativo |
| `possui_gd` | booleano | UC tem GD |
| `queda_explicada_por_gd` | booleano | a queda começou depois da conexão da GD (rebaixa ou exclui a UC) |
| `energia_injetada_atipica` | booleano | sinal da Silver de GD (log G5) |
| `qtd_inspecoes_anteriores` | inteiro | inspeções já feitas na UC (0 se nunca inspecionada) |
| `resultado_ultima_inspecao` | texto | `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE` (nulo se nunca inspecionada) |
| `data_ultima_inspecao` | data | data da última inspeção (`data_inspecao` da Silver; nulo se nunca inspecionada) |
| `municipio` | texto | município |
| `bairro` | texto | bairro |
| `classe` | texto | classe |
| `data_referencia_score` | data | data dos dados usados no cálculo (fim da base) |
| `versao_regra_score` | texto | versão da regra (ex.: `v1`), para rastrear mudanças na priorização |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| L2 e F2 | Órfãs removidas nas Silvers de leituras e faturas | as médias de consumo da `dim_uc` usam só leituras válidas |
| L5 | Troca de medidor: consumo = `leitura_atual` | as médias de 12 meses das UCs com troca usam esse consumo |
| Inspeções | `silver.inspecoes`: resultado normalizado em `IRREGULARIDADE CONFIRMADA` e `SEM IRREGULARIDADE` | 1.389 inspeções, 871 com irregularidade confirmada (62,7%); só as inspeções da Silver entram, e as registradas no portal **não** |

## Cuidados de uso

- **A regra v1 é nossa:** o contrato definiu os sinais e os cuidados; os **pesos, os limiares e os fatores de ajuste são decisões nossas** (parâmetros na seção 2 do notebook). Queda de consumo até 60 pontos; medidor eletromecânico 15; medidor com 15 anos ou mais 5; abaixo dos pares até 15; GD com injeção atípica 5. Ajustes: queda explicada por GD ×0,25 (e energia a recuperar zero), última inspeção sem irregularidade ×0,5, reincidência +5. Corte da fila: score de 40.
- **Validação retrospectiva, não independente:** score de 60 ou mais, 91,4% de irregularidade confirmada nas inspeções (831 de 909), contra 8,4% abaixo de 40 (referência histórica: 62,7%). Os pesos vieram da análise dos quatro bairros, que usa as mesmas inspeções.
- **O sinal de queda só foi validado nas UCs dos quatro bairros** do diagnóstico. Fora delas não há inspeções de UCs com queda forte, e as 29 UCs dispersas que a fila traz são o melhor teste com dados novos.
- **A fila tem duas populações:** 831 revisitas (irregularidade confirmada e consumo que não voltou, 94% da energia a recuperar), 32 UCs nunca inspecionadas e 43 com última inspeção sem irregularidade (rebaixadas). `qtd_inspecoes_anteriores` e `resultado_ultima_inspecao` permitem separar.
- **`kwh_estimado_recuperar_mes`** subestima as UCs com queda recente (≈ 87% da estimativa do diagnóstico), porque a janela anterior de 12 meses já contém meses depois da queda.
- **`consumo_vs_pares_pct`** é negativo quando a UC consome menos que a mediana dos pares sem GD (mínimo de 5 UCs no segmento); onde muitas UCs caíram juntas, a mediana também cai.
- Mudar a regra muda a `versao_regra_score`, e não as colunas.

## Como foi validada

- 20 colunas, `id_uc` único e `prioridade` contínua de 1 a 906; o score decresce com a prioridade.
- Toda UC da fila existe na `dim_uc`, com o mesmo município, bairro e classe; a soma de `qtd_inspecoes_anteriores` é 1.389.
- Energia a recuperar de 208.882 kWh por mês (≈ 2,5 milhões por ano).
