# Dicionário de dados · `gold.fato_troca_medidor`

> Contrato: tabela **A6** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fato_troca_medidor.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

As 6.299 trocas de medidor se concentram entre `2025-09` e `2026-03`, dentro dos últimos 12 meses do diagnóstico. A tabela responde se a troca mudou o volume medido (P1, Henrique) e mostra a troca na visão 360 quando o cliente diz que a conta veio alta (P5, Camila).

**Quem usa:** diagnóstico, visão 360, tela de receita (fator explicativo) e agente de IA.

**Grão:** 1 linha = 1 troca de medidor. Cada UC trocou o medidor uma única vez.

**Linhas:** 6.299. **Validação do próprio notebook:** 28 checagens, todas `PASS`.

**Fontes (Silver):** `leituras`, `medidores` e `unidades_consumidoras`.

## Colunas (13)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `id_uc` | texto | UC (chave: uma troca por UC) |
| `mes_troca` | texto | `yyyy-MM` da troca (de `2025-09` a `2026-03`, ~900 por mês) |
| `id_medidor_antigo` | texto | medidor retirado (o da leitura do mês anterior à troca) |
| `tipo_medidor_antigo` | texto | `ELETROMECANICO` (5.661), `ELETRONICO` (601) ou `SMART` (37) |
| `idade_medidor_antigo_anos` | decimal | anos entre a instalação e a **retirada** (dias ÷ 365,25, 1 casa); média de ~16 anos |
| `id_medidor_novo` | texto | medidor instalado (o que fez a leitura no mês da troca; é o `id_medidor_ativo` da `dim_uc`) |
| `tipo_medidor_novo` | texto | **sempre `SMART`** nesta base |
| `consumo_medio_6m_antes` | decimal | média mensal do consumo nos 6 meses anteriores ao mês da troca (menos em 10 UCs novas; ver abaixo) |
| `consumo_medio_6m_depois` | decimal | média mensal do consumo nos meses seguintes à troca, até 6 (de 3 a 6, porque a base termina em `2026-06`) |
| `variacao_consumo_pct` | decimal | `(depois ÷ antes − 1) × 100`, 2 casas. **Mistura o efeito da troca com o da estação do ano** |
| `classe` | texto | classe da UC |
| `municipio` | texto | município da UC |
| `bairro` | texto | bairro da UC (usar sempre junto com `municipio`) |

## Decisões que afetam esta tabela

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| L5 | Troca de medidor: a leitura anterior é do medidor antigo, e o consumo do mês sai negativo (6.299) | na Silver, `consumo = leitura_atual` + flag `troca_medidor`. Aqui, **o mês da troca fica fora das duas médias**, porque o critério do consumo é diferente nele |
| M2 | `data_retirada` com a sentinela `9999-12-31` nos ativos | nulo na Silver; o antigo de toda troca tem data de retirada real, no mês da troca |
| M4 | `data_instalacao` em 4 formatos | convertida na Silver; o medidor novo foi instalado no mês da troca em 100% das trocas |
| M5 | Tipo do medidor com 10 grafias | normalizado na Silver para os 3 tipos |
| Janela | 10 trocas de UCs ligadas entre `2025-05` e `2025-12` | a média de antes usa os meses desde a 1ª leitura (de 1 a 5). O medidor retirado delas tinha de 0,1 a 0,6 ano |

## Cuidados de uso

- **`variacao_consumo_pct` sobe por causa da estação, e não da troca.** As trocas são de setembro a março: os 6 meses antes caem no inverno (consumo baixo) e os seguintes, no verão. Para medir o efeito da troca, comparar com as UCs que não trocaram, nas mesmas janelas (seção 9 do notebook).
- **A troca não mudou o volume medido.** Descontada a estação (comparação com as UCs sem troca e sem GD), o efeito médio é de **+0,4 ponto percentual**; mês a mês, de −3,2 a +1,4 p.p., com exceção de `2025-11` (+7,8 p.p., sem explicação nos dados). A troca não explica a queda de volume do diagnóstico.
- **Foi um programa de substituição por medidor inteligente:** todos os novos são `SMART`, e 90% dos retirados eram eletromecânicos (idade média de ~16 anos). Até medidores com poucos meses de uso foram trocados.
- **Para a visão 360 ("conta alta"):** no mês da troca, o consumo é a leitura atual do medidor novo e o preço por kWh fica ~5% acima do típico (log L5). A flag `troca_medidor` da `fato_consumo_faturamento` marca esse mês; esta tabela dá o contexto (tipo e idade do medidor antigo).
- **As trocas de `2026-01` a `2026-03` têm menos meses depois** (de 5 a 3), então a média de depois é menos estável.
- **As UCs com GD estão na tabela.** Se a GD foi conectada perto da troca, a queda de consumo é da GD, e não da troca; filtrar pela `dim_uc` (`possui_gd`, `data_conexao_gd`) quando for comparar consumo.

## Como foi validada

- 6.299 trocas, uma por UC, iguais às leituras com `troca_medidor`; todas entre `2025-09` e `2026-03`.
- Medidor antigo diferente do novo, os dois da mesma UC; antigo `RETIRADO` com retirada no mês da troca e novo `ATIVO` instalado no mês da troca, em 100%.
- 6 meses antes em todas as trocas (exceto as 10 UCs novas, com todos os meses desde a 1ª leitura); de 3 a 6 meses depois.
- Conexão com a `dim_uc`: 0 UCs fora; as 6.299 têm `medidor_trocado_recentemente = true`, e o medidor novo é o `id_medidor_ativo` da dimensão.
