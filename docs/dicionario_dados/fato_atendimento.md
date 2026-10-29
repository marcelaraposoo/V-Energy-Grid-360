# Dicionário de dados · `gold.fato_atendimento`

> Contrato: tabela **B1** do contrato da Gold (v4) · Notebook: `data-engineering/notebooks/03_gold_fato_atendimento.ipynb` · Status: executada; `PASS` em todas as checagens

## Para que serve

A Camila quer ver "os chamados que ele já abriu" na visão 360; também permite ao agente responder sobre atendimento.

**Quem usa:** visão 360 (chamados do cliente), KPIs mensais e agente de IA.

**Grão:** 1 linha = 1 chamado (protocolo). 318.871 linhas.

**Linhas:** 318.871 (1 por chamado). **Validação do próprio notebook:** 36 checagens, todas `PASS`.

## Colunas (16)

As definições seguem o contrato da Gold (v4). Os tipos são os lógicos do contrato; no `gold.db` (SQLite), texto e data viram `TEXT`, inteiro e booleano viram `INTEGER` (0/1) e decimal vira `REAL`.

| Coluna | Tipo | Definição |
|---|---|---|
| `protocolo` | texto | identificador do chamado (`AT` + 9 dígitos) |
| `id_uc` | texto | UC |
| `municipio` | texto | município da UC |
| `bairro` | texto | bairro da UC |
| `classe` | texto | classe da UC |
| `canal` | texto | canal de abertura: `TELEFONE`, `APP`, `WHATSAPP`, `SITE` ou `PRESENCIAL` |
| `assunto` | texto | `FALTA DE ENERGIA`, `FATURA`, `DANO ELETRICO`, `LIGACAO NOVA`, `GERACAO DISTRIBUIDA` ou `RELIGACAO` |
| `subassunto` | texto | detalhe do assunto: `VISTORIA`, `INTERRUPCAO PARCIAL`, `INTERRUPCAO TOTAL`, `OSCILACAO`, `URGENCIA`, `RESSARCIMENTO`, `APOS PAGAMENTO`, `SOLICITACAO`, `HOMOLOGACAO`, `PRAZO`, `CREDITOS`, `CONTESTACAO`, `SEGUNDA VIA`, `VALOR ALTO` ou `PARCELAMENTO` (15 valores, formando 17 pares com o assunto; cada subassunto pertence a um único assunto, exceto `VISTORIA`, que aparece em `DANO ELETRICO`, `GERACAO DISTRIBUIDA` e `LIGACAO NOVA`) |
| `data_hora_abertura` | data e hora | abertura (**com horário**: não converter para data) |
| `data_hora_fechamento` | data e hora | fechamento (nulo se em aberto; **com horário**) |
| `mes_referencia` | texto | `yyyy-MM` da abertura |
| `aberto` | booleano | chamado sem fechamento. **`false` em todos os chamados desta base**: a lista de chamados abertos da visão 360 sai vazia, e esse é o dado correto |
| `tempo_resolucao_horas` | decimal | horas entre abertura e fechamento, 2 casas (de 1 a 719 h nesta base; nulo se aberto) |
| `qtd_tratativas` | inteiro | ações registradas no histórico (1 a 3) |
| `ultima_acao` | texto | **última ação registrada** no histórico: `ABERTURA`, `ANALISE`, `DESPACHO`, `RETORNO AO CLIENTE` ou `ENCERRAMENTO`. **Não indica a situação do chamado** (log A5): para isso, usar `aberto` |
| `nota_satisfacao` | decimal | nota de 1 a 5, com 1 casa decimal (de 1,3 a 5,0 nesta base); nula quando o cliente não avaliou (9.566 chamados, 3,0%) |

## Decisões de limpeza que afetam esta tabela

Os itens são do `docs/data_quality_log.md`.

| Item | O que foi encontrado | O que foi feito, e o efeito aqui |
|---|---|---|
| A1 | `nota_satisfacao` nula, chamado não avaliado (9.566; 3,0%) | mantida nula (nulo de negócio); convertida para decimal |
| A2 | Acúmulo de notas em 5,0 (6.160, contra 4.363 em 4,9) | não alterado; hipótese de corte, sem evidência para corrigir |
| A3 | `historico` aninhado (636.857 tratativas) | aberto na tabela `silver.tratativas_atendimento`; esta tabela traz só `qtd_tratativas` e `ultima_acao` |
| A4 | Datas em texto, em dois formatos | convertidas para data e hora, **sem cast para data**; horários locais, sem fuso |
| A5 | A última ação não indica a situação do chamado | não se deriva status da ação; usa-se `aberto` |
| A6 | Pico de julho de 2025: 18.061 chamados, ~2,8× o normal | mantido (é um evento real, coerente com a rede no mesmo mês) |
| A7 | `data_fechamento` nulo = chamado em aberto | flag `aberto`; **falsa em todos os chamados desta base** |

## Cuidados de uso

- **`aberto` é falso em todos os chamados desta base:** não há chamados em aberto. O **histórico de chamados do cliente** (todos os que ele já abriu) aparece normalmente na visão 360.
- **`ultima_acao` é a última ação registrada, e não a situação do chamado.** "Quantos chamados foram encerrados?" não se responde com `ultima_acao = 'ENCERRAMENTO'` (63.432), e sim com todos os chamados fechados (`aberto = false`: 318.871).
- **`mes_referencia` é o mês de abertura do chamado**; na `fato_consumo_faturamento` é a competência da fatura.
- **`2025-07` tem 18.061 chamados**, e a alta de 16% entre o primeiro ano e os últimos 12 meses vem quase toda desse mês (sem o excesso, ~0,8%). O tempo até fechar sobe de ~120 h para ~361 h e a nota cai de ~4,10 para ~3,11.
- **A nota média é 4,04 em todos os canais**: o canal de abertura não muda a satisfação nesta base. A média usa só as notas preenchidas, na escala de 1 a 5.
- **Horários locais, sem fuso:** o `Z` que o Databricks exibe é só a exibição; não converter fuso.
- Os **17 pares assunto × subassunto** saem desta tabela (`SELECT DISTINCT assunto, subassunto`); `VISTORIA` é o único subassunto em mais de um assunto.

## Como foi validada

- 318.871 chamados, igual à `silver.atendimentos`; a soma de `tempo_resolucao_horas` é idêntica (42.590.583 h).
- 9.566 notas nulas, 17 pares assunto × subassunto e 18.061 chamados em 2025-07.
- Primeiro ano 76.561 chamados e últimos 12 meses 88.823 (+16,0%).
- 0 UCs com chamado fora da `dim_uc` e 0 com município, bairro ou classe diferentes.
