# Contrato da Gold — v5 (final)

Formato das tabelas que a camada Gold entrega ao portal (Dev), ao agente (IA) e ao diagnóstico da receita.
Este contrato guiou a construção da Gold: Dev e IA trabalharam com dados de exemplo **neste formato** enquanto as tabelas não ficavam prontas.

**Status:** **as 10 tabelas estão implementadas**, com todas as checagens de qualidade passando, e rodam pelo Workflow `v_energy_pipeline` (ver o README). O export entrega o `gold.db` (SQLite) para o backend e o agente. A definição de cada coluna, com as decisões de limpeza e os cuidados de uso, está no **[dicionário de dados](dicionario_dados/README.md)**, que é a referência final; este contrato registra **o que foi combinado e por quê**. Os códigos das tabelas (A1 a A8, B1 e B2) **não mudaram**. A Parte C lista o que **não** pertence à Gold (dados criados no portal, que ficam no banco do backend).

**Responsáveis pela Gold:** Aimê e Marcela (tabela na seção "Visão geral").

## O que mudou na v5 (implementação)

**Nenhuma coluna foi removida, renomeada ou mudou de tipo.** A v5 registra o que a implementação decidiu onde o contrato não era explícito, e fecha as pendências.

| Tabela | O que a implementação definiu |
|---|---|
| Todas | **Implementadas** (linhas e checagens na "Visão geral"); log de qualidade de todas em `silver.dq_log` |
| A3 `fato_segmento_mensal` | Os 1.106 segmentos existem nos 48 meses (53.088 linhas). A soma dos segmentos de cada mês é **igual** à `kpis_mensal`, e os dois períodos somados por segmento são **iguais** à `receita_decomposicao` |
| A6 `fato_troca_medidor` | **O mês da troca fica fora** das médias de antes e depois (o consumo dele é a leitura atual, L5). As 10 UCs ligadas há menos de 6 meses usam os meses desde a 1ª leitura |
| A7 `fato_interrupcao` | **Causa nula = `causa_evitavel` falso** (sem a causa, não dá para dizer que a manutenção evitaria): as horas evitáveis são um piso |
| A8 `dec_fec_alimentador_mensal` | `dec_12m_horas` e `fec_12m` = soma dos 12 meses até o mês, **nulos de `2022-07` a `2023-05`** (menos de 12 meses de base). `causa_principal` considera só as causas informadas. Ranking sem empates (desempate pelas horas interrompidas). 584 ocorrências antes da ligação da UC mantidas (log X1) |
| B2 `fila_inspecao` | **Regra v1 implementada** (seção B2), com fontes `dim_uc` e Silver de inspeções |
| Pendências | Máscara LGPD aplicada; `OSCILACAO` mantida no DEC/FEC; regra do score v1 implementada. Fica em aberto só a tela dos insights (IA) |

## O que mudou na v4

**Para Dev e IA: nenhuma coluna foi removida, renomeada ou mudou de tipo nas tabelas A1 a A8.** As mudanças nelas são esclarecimentos de regra. As únicas tabelas com colunas novas ou valores novos são B1 e B2, que estavam pendentes.

| Tabela | Tipo de mudança | O que mudou |
|---|---|---|
| B1 `fato_atendimento` | **Fechada** | Valores de `canal` (5), `assunto` (6) e `subassunto` (15); escala da nota (1 a 5, 1 casa decimal); `ultima_acao` passa a ser descrita como "última ação registrada", **não** como situação do chamado; tratativas **não** entram na Gold |
| B2 `fila_inspecao` | **Fechada (estrutura)** | Valores de `resultado_ultima_inspecao` (2); taxa de acerto histórica (62,7%) para calibrar a regra; proposta v1 da regra do `score` e da energia a recuperar, a validar na implementação |
| A5 `kpis_mensal` | Pendência fechada | Escala de `nota_satisfacao_media`: 1 a 5, média só das notas preenchidas |
| A2, A3, A5 | Regra esclarecida | "GD conectada até o mês" = `mes_referencia` **igual ou posterior** ao mês da conexão (inclui o mês da conexão). Mesma regra em `possui_gd_no_mes`, `qtd_ucs_com_gd` e `consumo_kwh_ucs_com_gd` |
| A2 `fato_consumo_faturamento` | Regra esclarecida | Limites de `faixa_atraso`; `variacao_consumo_ano_anterior_pct` nula em todo o primeiro ano; `dias_atraso` não mede inadimplência; 93% das faturas em aberto estão em `MAIS DE 90 DIAS` (orientação para a visão 360) |
| Convenções | Nova regra | GD no mês (acima) |
| Validação | Conferido | "Quase 300 bairros": 297 pares município + bairro (272 nomes de bairro) |

**Datas do atendimento (resolvido na implementação):** a `fato_atendimento` guarda **data e hora** em `data_hora_abertura` e `data_hora_fechamento`, sem cast para `date`, e o log A4 foi corrigido.

**Histórico:** a v3 incorporou os comentários de Dev e IA (`fato_segmento_mensal`, denominador do DEC/FEC por mês, grade completa com zeros, datas com horário, rastreabilidade do score, tabelas operacionais fora da Gold) e os números das Silvers de leituras, faturas, GD e ocorrências.

---

## Perguntas do case que a Gold precisa responder

Lista tirada das falas das lideranças e dos requisitos 5.1 a 5.4 do case. Cada tabela indica, em **Responde a**, quais destas perguntas ela atende. A cobertura completa está no fim do arquivo.

**Diagnóstico da receita (Henrique, Diretor Comercial; requisito 5.4)**
- **P1.** A base cresceu e a tarifa residencial subiu 10,5% desde 2022. Por que, comparando os últimos 12 meses com o primeiro ano, o volume faturado caiu quase 4% e a receita subiu só 8%? A resposta precisa de causas sustentadas com dados e de recomendações com ordem de grandeza do impacto.
- **P2.** Quanto da variação da receita foi preço e quanto foi volume? Investigar por município, bairro e classe até achar onde está a queda e por quê.

**Painel da diretoria (requisito 5.2)**
- **P3.** Quais são os principais indicadores do negócio, e como eles se comparam entre períodos ("estamos indo bem ou mal?")?

**Visão 360 do atendimento (Camila, Gerente de Atendimento)**
- **P4.** Para uma UC, numa tela só: quem é o cliente, o consumo dos últimos meses ao lado do mesmo período do ano anterior, as faturas em aberto, o medidor instalado, se tem painel solar, se a rua teve falta de luz e os chamados já abertos.
- **P5.** Quando o cliente diz que a conta veio alta: o consumo realmente subiu?

**Perdas (Rafael, Gerente de Perdas)**
- **P6.** Qual é a fila de UCs suspeitas, da mais à menos promissora, com o motivo da suspeita e a energia estimada a recuperar?
- **P7.** Gerar ordens de inspeção a partir da fila, atualizar o status, registrar o resultado e cancelar. Diferenciais: exportar a fila e subir a planilha preenchida em campo.

**Qualidade do serviço (Beatriz, Gerente de Operação; requisito 5.1)**
- **P8.** Qual é o DEC e o FEC de cada alimentador ao longo do tempo, e quais são os piores?
- **P9.** Quais regiões concentram as piores interrupções, e onde a manutenção preventiva dá mais retorno?

**Agente de IA (Patrícia, Diretora de Tecnologia; Henrique; requisito 5.3)**
- **P10.** Responder em português perguntas sobre consumo, faturamento, interrupções e atendimento, entendendo termos do dia a dia ("conta de luz", "falta de luz") e dizendo quando não sabe. Exemplos do case:
  - "Quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?"
  - "Qual bairro mais perdeu volume residencial no último ano?"
  - "Quanto a receita comercial cresceu em Jaboatão?"
- **P11.** Mostrar insights gerados por IA em pelo menos uma tela, sem o usuário precisar perguntar.

**Uso do portal e auditoria (requisitos 5.1 e 5.2)**
- **P12.** Filtrar e recortar as informações conforme a necessidade de cada usuário.
- **P13.** Publicar um dicionário de dados da Gold, com a definição de cada métrica e as decisões de limpeza que a afetam.

---

## Convenções

- **Tipos:** texto, inteiro, decimal, data, data e hora (`timestamp`), booleano.
- **Mês:** `mes_referencia` como texto `yyyy-MM` (ordena corretamente e funciona em SQLite e Postgres).
- **Datas com horário:** interrupções e atendimentos guardam **data e hora** (a origem traz o horário). Faturas, leituras, inspeções e cadastro guardam só a data.
- **Nomes:** `snake_case`, sem acento. `dim_*` descreve entidades; `fato_*` registra eventos ou medições; as demais são agregadas para telas específicas.
- **Chave:** `id_uc` é a chave de todas as tabelas por UC. A `dim_uc` **não** terá chave substituta (`uc_sk`): o `id_uc` é único, estável e já usado em todas as Silvers. Desvio consciente do padrão da aula, registrado no notebook.
- **Dados pessoais (LGPD):** CPF/CNPJ e nome do titular **nunca** saem da Silver sem máscara.
- **Bairro:** o mesmo nome de bairro existe em municípios diferentes (297 pares município + bairro, 272 nomes). Todo agrupamento, filtro ou join por bairro usa **`municipio` + `bairro`**.
- **Receita:** `valor_energia` (sem tributos, com o adicional de bandeira embutido). `valor_total` aparece à parte.
- **Base de UCs:** 45.000. "Número de UCs" sempre vem com o adjetivo: **cadastradas** (ligadas até o fim do mês, pela `data_ligacao`) ou **faturadas** (com fatura no mês).
- **GD no mês (nova na v4):** uma UC tem "GD conectada até o mês" quando `mes_referencia` é **igual ou posterior** ao mês da `data_conexao` (o mês da conexão conta, mesmo que a GD tenha funcionado só parte dele). A mesma regra vale para `possui_gd_no_mes` (A2), `qtd_ucs_com_gd` e `consumo_kwh_ucs_com_gd` (A3 e A5) e `qtd_ucs_com_gd_1` (A4), para os números baterem entre as tabelas.
- **Períodos do diagnóstico:** primeiro ano = `2022-07` a `2023-06`; últimos 12 meses = `2025-07` a `2026-06`. Outros períodos são calculados pela API a partir da `fato_segmento_mensal`.
- **Fim da base:** 2026-06-30. Idades, dias de atraso e janelas de 12 meses são calculados até essa data.

---

## Visão geral

| # | Tabela | Grão | Quem usa | Responsável | Situação |
|---|---|---|---|---|---|
| A1 | `dim_uc` | 1 UC | Todas as telas, agente | Aimê | ✅ Implementada: 45.000 linhas, 26 checagens |
| A2 | `fato_consumo_faturamento` | 1 UC × 1 mês | Visão 360, agente, diagnóstico | Marcela | ✅ Implementada: 2.152.336 linhas, 52 checagens |
| A3 | `fato_segmento_mensal` | mês × município × bairro × classe | Dashboard (filtros), tela de receita (períodos livres), insights | Aimê | ✅ Implementada: 53.088 linhas, 47 checagens |
| A4 | `receita_decomposicao` | município × bairro × classe | Tela de receita, diagnóstico | Marcela | ✅ Implementada: 1.106 linhas, 35 checagens |
| A5 | `kpis_mensal` | 1 mês | Dashboard, agente | Marcela | ✅ Implementada: 48 linhas, 46 checagens |
| A6 | `fato_troca_medidor` | 1 troca | Diagnóstico, visão 360 | Aimê | ✅ Implementada: 6.299 linhas, 28 checagens |
| A7 | `fato_interrupcao` | 1 ocorrência (1 UC) | Visão 360, qualidade, agente | Aimê | ✅ Implementada: 180.000 linhas, 32 checagens |
| A8 | `dec_fec_alimentador_mensal` | 1 alimentador × 1 mês | Tela de qualidade, agente | Aimê | ✅ Implementada: 5.856 linhas, 38 checagens |
| B1 | `fato_atendimento` | 1 chamado | Visão 360, KPIs, agente | Marcela | ✅ Implementada: 318.871 linhas, 36 checagens |
| B2 | `fila_inspecao` | 1 UC suspeita | Tela de perdas | Marcela | ✅ Implementada (regra v1): 906 linhas, 32 checagens |

**Divisão:** cada uma fica com 5 tabelas. Aimê: as que usam cadastro, medidor, GD e rede (A1, A3, A6, A7, A8). Marcela: as que usam consumo, faturamento, atendimento e inspeções (A2, A4, A5, B1, B2).

---

# Parte A — Cadastro, consumo, faturamento e rede

## A1. `dim_uc`

**Por que existe:** é a "fonte única de verdade" sobre cada cliente (seção 3 do case). Responde ao "quem é o cliente", "o medidor instalado" e "se ele tem painel solar" da Camila, e dá os filtros por município, bairro e classe que o Henrique pede.
**Quem usa:** todas as telas (cabeçalho da visão 360, filtros) e o agente de IA.
**Responde a:** P4 (cliente, medidor, painel solar), P10 (filtros por município, bairro, classe e GD; exemplo de Olinda), P12 (filtros), P1 (GD, principal causa da queda de volume) e P6 (perfil do medidor e da GD para a fila).
**Grão:** 1 linha = 1 unidade consumidora (45.000 linhas).
**Fontes (Silver):** unidades_consumidoras, medidores, geracao_distribuida, leituras.

**Colunas:**
- `id_uc` | texto | identificador da UC (`UC` + 6 dígitos)
- `nome_titular_mascarado` | texto | primeiro nome + iniciais (ex.: `EDVALDO P*** B***`)
- `documento_mascarado` | texto | CPF: `***.816.240-**`; CNPJ: `**.***.816/0001-**`
- `tipo_pessoa` | texto | `PF` ou `PJ`
- `logradouro` | texto | rua
- `numero` | texto | número
- `bairro` | texto | bairro padronizado, com acentuação corrigida (usar sempre junto com `municipio`)
- `municipio` | texto | um dos 14 municípios da RMR, com o nome oficial (ex.: `Jaboatão dos Guararapes`)
- `uf` | texto | sempre `PE`
- `cep` | texto | 8 dígitos, sem hífen (nulo em 1.193 UCs com CEP inválido na origem; log U7)
- `latitude` | decimal | latitude
- `longitude` | decimal | longitude
- `classe` | texto | `RESIDENCIAL`, `RURAL`, `COMERCIAL`, `PODER PUBLICO` ou `INDUSTRIAL`
- `subgrupo_tarifario` | texto | `B1` (residencial), `B2` (rural), `B3` (comercial e poder público), `A4` (industrial)
- `alimentador` | texto | circuito que abastece a UC (ex.: `ALM-REC-004`; as 3 letras do meio são o município)
- `data_ligacao` | data | data de ligação da UC
- `data_ligacao_estimada` | booleano | `true` nas 90 UCs cuja data de origem era impossível (antes de 1950); nelas, a data é a instalação do 1º medidor (log U9)
- `status` | texto | sempre `ATIVA` nesta base
- `id_medidor_ativo` | texto | medidor instalado hoje (toda UC tem exatamente 1)
- `tipo_medidor_ativo` | texto | `ELETRONICO`, `ELETROMECANICO` ou `SMART`
- `modelo_medidor_ativo` | texto | modelo (ex.: `EL-3000`)
- `data_instalacao_medidor` | data | instalação do medidor ativo
- `idade_medidor_anos` | decimal | anos entre a instalação e o fim da base
- `medidor_trocado_recentemente` | booleano | UC teve troca de medidor entre 2025-09 e 2026-03
- `possui_gd` | booleano | UC tem geração distribuída (painel solar); 3.510 UCs
- `potencia_gd_kwp` | decimal | potência instalada (nulo se não tiver GD; 35 convertidas de watts, log G2)
- `data_conexao_gd` | data | data de conexão da GD (nulo se não tiver)
- `modalidade_gd` | texto | `GERACAO NA PROPRIA UC`, `AUTOCONSUMO REMOTO` ou `GERACAO COMPARTILHADA` (nulo se não tiver)
- `energia_injetada_media_kwh` | decimal | energia injetada média por mês (**não usar como medida** quando `energia_injetada_atipica = true`)
- `energia_injetada_atipica` | booleano | energia injetada provavelmente calculada, e não medida (109 UCs; log G5)
- `primeiro_mes_leitura` | texto | primeiro `mes_referencia` com leitura
- `ultimo_mes_leitura` | texto | último `mes_referencia` com leitura
- `consumo_medio_12m_kwh` | decimal | consumo médio mensal de `2025-07` a `2026-06`
- `consumo_medio_12m_anterior_kwh` | decimal | consumo médio mensal de `2024-07` a `2025-06`
- `variacao_consumo_12m_pct` | decimal | variação entre os dois (responde "queda acima de 30%"; também alimenta a fila)

---

## A2. `fato_consumo_faturamento`

**Por que existe:** une medição e faturamento, que hoje vivem em sistemas separados. Responde ao "consumo dos últimos meses ao lado do mesmo período do ano passado" e às "faturas em aberto" da Camila (inclusive "quando ele reclama de conta alta"), e é a base das contas de volume e receita do Henrique.
**Quem usa:** visão 360 (gráfico de consumo e lista de faturas), agente de IA, diagnóstico; base das tabelas agregadas.
**Responde a:** P4 (consumo vs ano anterior, faturas em aberto), P5 (conta alta: consumo e valor no mesmo intervalo), P10 (consumo e faturamento por UC, bairro, classe e mês) e P1 (base do diagnóstico).
**Grão:** 1 linha = 1 UC em 1 mês de referência (1 leitura + 1 fatura; as Silvers garantem exatamente uma de cada: 2.152.336 pares).
**Fontes (Silver):** leituras, faturas, unidades_consumidoras, geracao_distribuida.
**Situação:** implementada (Marcela, 31 colunas, 52 checagens `PASS`). Reproduz volume −3,95% e receita de energia +8,00%. Conexão com a `dim_uc` testada: 0 UCs fora.

**Colunas:**
- `id_uc` | texto | UC
- `mes_referencia` | texto | competência `yyyy-MM`
- `ano` | inteiro | ano da competência
- `mes` | inteiro | mês da competência (1 a 12)
- `periodo_diagnostico` | texto | `PRIMEIRO_ANO` (`2022-07` a `2023-06`), `ULTIMOS_12M` (`2025-07` a `2026-06`) ou `OUTRO`
- `classe` | texto | classe da UC (repetida para facilitar consultas do agente)
- `bairro` | texto | bairro da UC
- `municipio` | texto | município da UC
- `possui_gd_no_mes` | booleano | UC já tinha GD conectada neste mês (regra "GD no mês" das convenções: inclui o mês da conexão)
- `id_medidor` | texto | medidor que fez a leitura
- `data_leitura` | data | data da leitura
- `tipo_leitura` | texto | `REAL` ou `ESTIMADA`
- `consumo_kwh` | inteiro | consumo do mês, já tratado (L4, L5). **No mês de troca de medidor, é a leitura atual do medidor novo**: essa regra reproduz o −4% do diretor
- `consumo_kwh_ano_anterior` | inteiro | mesma UC, mesmo mês do ano anterior (nulo se não houver)
- `variacao_consumo_ano_anterior_pct` | decimal | variação em % sobre o ano anterior. **Nula em todo o primeiro ano** (`2022-07` a `2023-06`) e nos meses de UCs que ainda não existiam um ano antes
- `troca_medidor` | booleano | mês da troca de medidor (L5)
- `consumo_corrigido` | booleano | consumo com sinal corrigido (L4)
- `leitura_anterior_ausente` | booleano | leitura anterior faltante (L3)
- `id_fatura` | texto | fatura do mês
- `data_emissao` | data | emissão
- `data_vencimento` | data | vencimento
- `data_pagamento` | data | pagamento (nulo se em aberto)
- `valor_energia` | decimal | valor da energia, sem tributos, **com o adicional de bandeira embutido** (é a receita do diagnóstico)
- `tributos` | decimal | tributos
- `valor_total` | decimal | total da fatura
- `bandeira_tarifaria` | texto | `Verde`, `Amarela`, `Vermelha P1` ou `Vermelha P2` (só o nome; o valor do adicional não vem separado)
- `status_fatura` | texto | `PAGA` ou `EM ABERTO`
- `em_aberto` | booleano | fatura não paga
- `dias_atraso` | inteiro | dias entre vencimento e pagamento (ou até 2026-06-30, se em aberto); 0 se pago em dia ou se ainda não venceu
- `faixa_atraso` | texto | `EM DIA` (0), `ATE 30 DIAS` (1 a 30), `31 A 90 DIAS` (31 a 90) ou `MAIS DE 90 DIAS` (mais de 90)
- `preco_medio_kwh` | decimal | `valor_energia / consumo_kwh`

**Faturas em aberto na visão 360:** são 172.553 (8,0%), e **160.318 delas (93%) estão em `MAIS DE 90 DIAS`**, vindas de todos os anos desde 2022. Só 12.235 são recentes (até 90 dias ou ainda não vencidas). A Gold guarda todas; a sugestão é a visão 360 mostrar por padrão só as recentes e deixar as antigas atrás de um filtro por `faixa_atraso`. **Decisão de Dev** (Kauanny e Pilly).

**`dias_atraso` não mede inadimplência:** 83% das faturas pagas têm algum atraso (média de 10,8 dias contando as pagas em dia; máximo de 25). A inadimplência é por competência: % do valor em aberto de cada mês (A5).

---

## A3. `fato_segmento_mensal`

**Por que existe:** pedido de Dev. A `kpis_mensal` tem uma linha por mês e não permite filtrar por município, bairro ou classe. E a `receita_decomposicao` só compara os dois períodos fixos do diagnóstico, mas a tela de receita precisa de períodos escolhidos pelo usuário. Esta tabela agrega o consumo e a receita por segmento e mês: o dashboard filtra direto nela, e a API calcula a decomposição preço × volume para **qualquer par de períodos** com as fórmulas da A4.
**Quem usa:** dashboard executivo (com filtros), tela de receita (períodos livres e drill-down), insights de IA, agente.
**Responde a:** P3 (indicadores por segmento), P2 (decomposição em qualquer período), P12 (filtros), P10 ("qual bairro mais perdeu volume residencial no último ano") e P11 (base dos insights).
**Grão:** 1 linha = 1 mês × 1 município × 1 bairro × 1 classe (só combinações que existem).
**Fontes (Gold):** `fato_consumo_faturamento`, `dim_uc`.

**Colunas:**
- `mes_referencia` | texto | `yyyy-MM`
- `municipio` | texto | município
- `bairro` | texto | bairro
- `classe` | texto | classe
- `qtd_ucs_cadastradas` | inteiro | UCs do segmento ligadas até o fim do mês
- `qtd_ucs_faturadas` | inteiro | UCs do segmento com fatura no mês
- `qtd_ucs_com_gd` | inteiro | UCs do segmento com GD conectada até o mês (regra "GD no mês"; igual a contar `possui_gd_no_mes = true` na A2)
- `consumo_kwh` | decimal | energia faturada
- `consumo_kwh_ucs_com_gd` | decimal | parte do consumo vinda de linhas com `possui_gd_no_mes = true`
- `receita_energia` | decimal | soma de `valor_energia`
- `receita_total` | decimal | soma de `valor_total`
- `qtd_faturas` | inteiro | faturas do mês
- `qtd_faturas_em_aberto` | inteiro | faturas desta competência ainda em aberto
- `valor_em_aberto` | decimal | `valor_total` das faturas desta competência em aberto
- `qtd_faturas_bandeira_nao_verde` | inteiro | faturas com bandeira diferente de verde
- `qtd_trocas_medidor` | inteiro | trocas de medidor no mês

**Regra para a API:** decomposição de dois períodos quaisquer = somar `consumo_kwh` e `receita_energia` de cada período e aplicar as fórmulas da A4 (inclusive a regra de volume zero).

---

## A4. `receita_decomposicao`

**Por que existe:** responde à pergunta central do case. O Henrique: "quero ver por bairro e por classe, e quero saber quanto da variação foi preço e quanto foi quantidade de energia. Se foi volume, quero saber onde e por quê." É a versão **fixa e auditada** dos dois períodos do diagnóstico; para outros períodos, a tela usa a A3.
**Quem usa:** tela de receita (drill-down município → bairro → classe, waterfall), diagnóstico, insights de IA, agente.
**Responde a:** P2 (efeito-preço × efeito-volume por município, bairro e classe), P1 (onde está a queda e quanto vem da GD) e P10 (perda de volume por bairro e classe).
**Grão:** 1 linha = 1 combinação município × bairro × classe, comparando o primeiro ano (0) com os últimos 12 meses (1).
**Fontes (Gold):** `fato_consumo_faturamento` (a GD no fim do período 1 vem do `possui_gd_no_mes` dela).

**Fórmulas** (V = volume; P = receita / volume):
- `efeito_volume = (V1 − V0) × P0`
- `efeito_preco = (P1 − P0) × V1`
- `efeito_volume + efeito_preco = receita_1 − receita_0` (soma exata)
- **Volume zero em um dos períodos** (segmento sem faturas): o preço do período fica nulo, `efeito_volume = receita_1 − receita_0` e `efeito_preco = 0`.

**Colunas:**
- `municipio` | texto | município
- `bairro` | texto | bairro
- `classe` | texto | classe
- `qtd_ucs_periodo_0` | inteiro | UCs com fatura no primeiro ano
- `qtd_ucs_periodo_1` | inteiro | UCs com fatura nos últimos 12 meses
- `volume_kwh_0` | decimal | energia faturada no primeiro ano
- `volume_kwh_1` | decimal | energia faturada nos últimos 12 meses
- `receita_0` | decimal | soma de `valor_energia` no primeiro ano
- `receita_1` | decimal | soma de `valor_energia` nos últimos 12 meses
- `preco_medio_0` | decimal | `receita_0 / volume_kwh_0`
- `preco_medio_1` | decimal | `receita_1 / volume_kwh_1`
- `variacao_receita` | decimal | `receita_1 − receita_0`
- `variacao_receita_pct` | decimal | variação em %
- `variacao_volume_pct` | decimal | variação do volume em %
- `efeito_preco` | decimal | parte da variação explicada pelo preço (reajuste + bandeira)
- `efeito_volume` | decimal | parte da variação explicada pelo volume
- `consumo_medio_uc_0` | decimal | `volume_kwh_0 / qtd_ucs_periodo_0`
- `consumo_medio_uc_1` | decimal | `volume_kwh_1 / qtd_ucs_periodo_1`
- `qtd_ucs_com_gd_1` | inteiro | UCs com GD conectada até o fim do período 1 (regra "GD no mês" aplicada a `2026-06`)
- `volume_kwh_ucs_com_gd_0` | decimal | volume, no período 0, das UCs que têm GD no fim do período 1
- `volume_kwh_ucs_com_gd_1` | decimal | volume dessas mesmas UCs no período 1 (a diferença é a queda associada à GD)
- `qtd_trocas_medidor_1` | inteiro | trocas de medidor no período 1
- `pct_faturas_bandeira_nao_verde_0` | decimal | % de faturas não verdes no primeiro ano (0% nos dados)
- `pct_faturas_bandeira_nao_verde_1` | decimal | idem nos últimos 12 meses (~67% nos dados)

**Bandeira:** o adicional não vem separado, então o efeito é **estimado** no diagnóstico. No residencial, o preço subiu ~13% contra 10,5% de reajuste; a diferença, ~2,3% (1,130 ÷ 1,105 − 1, porque as taxas se compõem), é atribuída à bandeira. Para medir em vez de estimar: comparar, no mesmo mês e classe, o preço por kWh das faturas verdes e não verdes.

---

## A5. `kpis_mensal`

**Por que existe:** user story do diretor: "ver os principais indicadores do negócio e compará-los entre períodos, para saber rapidamente se estamos indo bem ou mal". É o resumo da empresa inteira; para recortes por município, bairro ou classe, o dashboard usa a A3.
**Quem usa:** dashboard executivo (cards e gráficos), agente de IA, diagnóstico.
**Responde a:** P3 (indicadores e comparação entre períodos), P1 (evolução mês a mês de volume, preço, bandeira e GD), P10 e P11.
**Grão:** 1 linha = 1 mês de referência (`2022-07` a `2026-06`).
**Fontes (Gold):** `fato_consumo_faturamento`, `dim_uc`, `fato_interrupcao`, `fato_atendimento`.

**Colunas:**
- `mes_referencia` | texto | `yyyy-MM`
- `qtd_ucs_cadastradas` | inteiro | UCs ligadas até o fim do mês
- `qtd_ucs_faturadas` | inteiro | UCs com fatura no mês
- `consumo_total_kwh` | decimal | energia faturada no mês
- `receita_energia` | decimal | soma de `valor_energia`
- `receita_total` | decimal | soma de `valor_total` (com tributos)
- `preco_medio_kwh` | decimal | `receita_energia / consumo_total_kwh`
- `bandeira_predominante` | texto | bandeira com mais faturas no mês
- `pct_faturas_bandeira_nao_verde` | decimal | % de faturas com bandeira diferente de verde
- `qtd_faturas_em_aberto` | inteiro | faturas **desta competência** ainda em aberto
- `inadimplencia_pct` | decimal | % do `valor_total` **desta competência** em aberto (não mistura dívida de meses anteriores)
- `valor_em_aberto_mais_90_dias` | decimal | valor desta competência em aberto há mais de 90 dias
- `qtd_ucs_com_gd` | inteiro | UCs com GD conectada até o mês (regra "GD no mês"; igual à soma da A3 no mês)
- `qtd_interrupcoes` | inteiro | ocorrências no mês
- `dec_horas` | decimal | DEC geral do mês (`minutos / 60 / qtd_ucs_cadastradas`)
- `fec` | decimal | FEC geral do mês (`ocorrências / qtd_ucs_cadastradas`)
- `qtd_atendimentos` | inteiro | chamados abertos no mês. **`2025-07` tem 18.061, cerca de 2,8× o normal** (evento climático; log A6)
- `nota_satisfacao_media` | decimal | média das notas do mês, **só das preenchidas**, na escala de 1 a 5 (os chamados sem avaliação não entram)
- `variacao_consumo_ano_anterior_pct` | decimal | consumo vs mesmo mês do ano anterior (nula de `2022-07` a `2023-06`)
- `variacao_receita_ano_anterior_pct` | decimal | receita vs mesmo mês do ano anterior (nula de `2022-07` a `2023-06`)

---

## A6. `fato_troca_medidor`

**Por que existe:** as 6.299 trocas de medidor se concentram entre 2025-09 e 2026-03, dentro dos últimos 12 meses do diagnóstico. Permite testar se a troca mudou o volume medido e mostrar a troca na visão 360 ("conta alta"). **Entra no escopo** (deixou de ser opcional).
**Quem usa:** diagnóstico; visão 360; tela de receita (fator explicativo).
**Responde a:** P1 (a troca mudou o volume medido?) e P5 (troca recente explica uma conta diferente).
**Grão:** 1 linha = 1 troca de medidor (6.299 linhas).
**Fontes (Silver):** medidores, leituras, unidades_consumidoras.

**Colunas:**
- `id_uc` | texto | UC
- `mes_troca` | texto | `yyyy-MM`
- `id_medidor_antigo` | texto | medidor retirado
- `tipo_medidor_antigo` | texto | tipo do retirado
- `idade_medidor_antigo_anos` | decimal | idade na retirada
- `id_medidor_novo` | texto | medidor instalado
- `tipo_medidor_novo` | texto | tipo do instalado
- `consumo_medio_6m_antes` | decimal | média dos 6 meses anteriores à troca (o mês da troca fica fora; nas 10 UCs ligadas há menos de 6 meses, os meses desde a 1ª leitura)
- `consumo_medio_6m_depois` | decimal | média dos meses após a troca (até 6; o mês da troca fica fora)
- `variacao_consumo_pct` | decimal | depois vs. antes. **Inclui o efeito da estação do ano** (as trocas são de setembro a março); o efeito da troca se mede contra as UCs que não trocaram (+0,4 ponto percentual: a troca não mudou o volume medido)
- `classe` | texto | classe da UC
- `municipio` | texto | município da UC
- `bairro` | texto | bairro da UC

---

## A7. `fato_interrupcao`

**Por que existe:** a Camila quer saber "se a rua dele teve falta de luz" na visão 360; é também a base para analisar interrupções por causa e local (Beatriz) e para o agente responder sobre "falta de luz".
**Quem usa:** visão 360, tela de qualidade (análise por causa e local), agente de IA.
**Responde a:** P4 (se a UC teve falta de luz), P9 (interrupções por causa e local) e P10 ("falta de luz").
**Grão:** 1 linha = 1 ocorrência de interrupção em 1 UC (180.000 linhas; glossário do case: cada registro é uma UC interrompida).
**Fontes (Silver):** ocorrencias_rede, unidades_consumidoras.

**Colunas:**
- `id_ocorrencia` | texto | identificador
- `id_uc` | texto | UC interrompida
- `alimentador` | texto | alimentador (sempre igual ao do cadastro da UC)
- `municipio` | texto | município da UC
- `bairro` | texto | bairro da UC
- `classe` | texto | classe da UC
- `tipo` | texto | `FALTA DE ENERGIA`, `DANO EM EQUIPAMENTO`, `OSCILACAO`, `SOBRECARGA` ou `FIO PARTIDO`
- `causa` | texto | `CLIMATICA`, `SOBRECARGA`, `NAO IDENTIFICADA`, `VEGETACAO`, `TERCEIROS` ou `FALHA DE EQUIPAMENTO` (nula em 5.400 ocorrências sem causa informada; log O1)
- `causa_evitavel` | booleano | `true` para `VEGETACAO`, `FALHA DE EQUIPAMENTO` e `SOBRECARGA` (evitáveis com manutenção preventiva); `false` nas demais **e na causa nula** (nunca nulo)
- `data_hora_inicio` | data e hora | abertura da ocorrência
- `data_hora_fim` | data e hora | encerramento (nenhuma ocorrência em aberto nesta base)
- `mes_referencia` | texto | `yyyy-MM` do início
- `duracao_min` | inteiro | duração em minutos (= fim − início em 100% das linhas)

**"A rua dele teve falta de luz":** esta tabela mostra se **a própria UC** ficou sem luz. Para mostrar a rua, o backend busca as ocorrências do mesmo alimentador ou do mesmo logradouro e bairro no período.

---

## A8. `dec_fec_alimentador_mensal`

**Por que existe:** a Beatriz: "a ANEEL cobra DEC e FEC da gente [...] quero acompanhar esses indicadores por alimentador, saber quais regiões concentram as piores interrupções e onde a manutenção preventiva dá mais retorno". Requisito 5.1: "calcular DEC e FEC por alimentador conforme a definição da ANEEL".
**Quem usa:** tela de qualidade do serviço (cards, evolução, ranking), agente de IA.
**Responde a:** P8 (DEC/FEC por alimentador ao longo do tempo e ranking), P9 (onde priorizar manutenção) e P10.
**Grão:** 1 linha = 1 alimentador × 1 mês, com **grade completa**: 122 alimentadores × 48 meses (`2022-07` a `2026-06`). Meses sem interrupção aparecem com DEC e FEC **zero**.
**Fontes (Gold):** `fato_interrupcao`, `dim_uc`.

**Fórmulas** (simplificadas, conforme o glossário: cada ocorrência = 1 UC interrompida):
- `dec_horas = soma(duracao_min) / 60 / qtd_ucs_alimentador_mes`
- `fec = qtd_interrupcoes / qtd_ucs_alimentador_mes`

**Colunas:**
- `alimentador` | texto | código do alimentador
- `municipio` | texto | município do alimentador (cada alimentador atende um único município)
- `mes_referencia` | texto | `yyyy-MM`
- `qtd_ucs_alimentador_mes` | inteiro | UCs do alimentador ligadas até o fim do mês (denominador)
- `qtd_interrupcoes` | inteiro | ocorrências no mês
- `horas_interrompidas` | decimal | soma das durações, em horas. Como cada ocorrência é uma UC, é também o total de **UC × horas** sem luz: a medida de impacto
- `qtd_interrupcoes_evitaveis` | inteiro | ocorrências com `causa_evitavel = true`
- `horas_causas_evitaveis` | decimal | horas dessas ocorrências (o que a manutenção preventiva poderia reduzir)
- `dec_horas` | decimal | duração equivalente por UC
- `fec` | decimal | frequência equivalente por UC
- `dec_12m_horas` | decimal | DEC acumulado dos 12 meses até este mês (soma dos DECs mensais); nulo de `2022-07` a `2023-05`
- `fec_12m` | decimal | FEC acumulado dos 12 meses até este mês; nulo de `2022-07` a `2023-05`
- `causa_principal` | texto | causa **informada** com mais horas no mês (nulo em mês sem interrupção)
- `ranking_dec_mes` | inteiro | posição do alimentador no mês (1 = pior DEC), de 1 a 122 sem empates

**Atenção ao denominador pequeno:** os piores DEC são de alimentadores com 20 a 47 UCs, em que poucas ocorrências já dão um indicador alto (as horas sem luz por ano variam pouco entre alimentadores, então o ranking de DEC reflete sobretudo o tamanho). A tela deve mostrar o DEC **junto** com `qtd_ucs_alimentador_mes` e `horas_interrompidas`, para a priorização não ir só para onde afeta pouca gente.
**Por bairro:** não atribuir o DEC do alimentador a cada bairro. Uma análise por bairro precisa de denominador próprio (UCs do bairro) e é feita a partir da `fato_interrupcao`.

---

# Parte B — Atendimento e perdas

As duas tabelas tinham pendências até a v3, porque dependiam das Silvers de atendimentos e inspeções. **Na v4, as duas estão definidas.** Os códigos B1 e B2 foram mantidos para não quebrar referências de Dev e IA.

## B1. `fato_atendimento`

**Por que existe:** a Camila quer ver "os chamados que ele já abriu" na visão 360; também permite ao agente responder sobre atendimento.
**Quem usa:** visão 360, KPIs (A5), agente de IA.
**Responde a:** P4 (chamados já abertos), P3 (volume de chamados e satisfação) e P10 (perguntas sobre atendimento).
**Grão:** 1 linha = 1 chamado (protocolo). 318.871 linhas.
**Fontes (Silver):** atendimentos, tratativas_atendimento (só para `ultima_acao`), unidades_consumidoras.

**Colunas:**
- `protocolo` | texto | identificador do chamado (`AT` + 9 dígitos)
- `id_uc` | texto | UC
- `municipio` | texto | município da UC
- `bairro` | texto | bairro da UC
- `classe` | texto | classe da UC
- `canal` | texto | canal de abertura: `TELEFONE`, `APP`, `WHATSAPP`, `SITE` ou `PRESENCIAL`
- `assunto` | texto | `FALTA DE ENERGIA`, `FATURA`, `DANO ELETRICO`, `LIGACAO NOVA`, `GERACAO DISTRIBUIDA` ou `RELIGACAO`
- `subassunto` | texto | detalhe do assunto: `VISTORIA`, `INTERRUPCAO PARCIAL`, `INTERRUPCAO TOTAL`, `OSCILACAO`, `URGENCIA`, `RESSARCIMENTO`, `APOS PAGAMENTO`, `SOLICITACAO`, `HOMOLOGACAO`, `PRAZO`, `CREDITOS`, `CONTESTACAO`, `SEGUNDA VIA`, `VALOR ALTO` ou `PARCELAMENTO` (15 valores, formando 17 pares com o assunto; cada subassunto pertence a um único assunto, exceto `VISTORIA`, que aparece em `DANO ELETRICO`, `GERACAO DISTRIBUIDA` e `LIGACAO NOVA`)
- `data_hora_abertura` | data e hora | abertura (**com horário**: não converter para data)
- `data_hora_fechamento` | data e hora | fechamento (nulo se em aberto; **com horário**)
- `mes_referencia` | texto | `yyyy-MM` da abertura
- `aberto` | booleano | chamado sem fechamento. **`false` em todos os chamados desta base**: a lista de chamados abertos da visão 360 sai vazia, e esse é o dado correto
- `tempo_resolucao_horas` | decimal | horas entre abertura e fechamento, 2 casas (de 1 a 719 h nesta base; nulo se aberto)
- `qtd_tratativas` | inteiro | ações registradas no histórico (1 a 3)
- `ultima_acao` | texto | **última ação registrada** no histórico: `ABERTURA`, `ANALISE`, `DESPACHO`, `RETORNO AO CLIENTE` ou `ENCERRAMENTO`. **Não indica a situação do chamado** (log A5): para isso, usar `aberto`
- `nota_satisfacao` | decimal | nota de 1 a 5, com 1 casa decimal (de 1,3 a 5,0 nesta base); nula quando o cliente não avaliou (9.566 chamados, 3,0%)

**Pares assunto × subassunto:** a lista dos 17 pares sai da Silver (`SELECT DISTINCT assunto, subassunto`) e vai para o dicionário de dados, para Dev montar filtros dependentes.

**Decisões da v4:**
1. **Tratativas fora da Gold.** A visão 360 só precisa de `qtd_tratativas` e `ultima_acao`. Se a tela de detalhe do chamado precisar do histórico completo, a `silver.tratativas_atendimento` (chave `protocolo` + `sequencia`) pode virar uma tabela da Gold numa versão futura, sem mudar esta.
2. **Escala da nota:** 1 a 5. Médias usam só as notas preenchidas.
3. **Datas com horário**, como pedido por Dev na v3.

**Para o dicionário de dados e os insights:** o pico de julho de 2025 (18.061 chamados, 2,8× o normal) explica quase toda a alta de chamados entre os dois períodos do diagnóstico (+16%; sem o excesso de julho, ~0,8%). No mesmo mês, o tempo até fechar sobe de ~120 h para ~361 h e a nota cai de ~4,10 para ~3,11. Há também um acúmulo de notas em 5,0 (6.160 contra 4.363 em 4,9), registrado como hipótese (log A2).

## B2. `fila_inspecao`

**Por que existe:** o Rafael: "quero abrir o sistema e ver uma fila das unidades suspeitas, da mais promissora para a menos promissora, com o motivo da suspeita e quanta energia dá para recuperar em cada uma. [...] Uma lista com mil nomes sem ordem não me serve".
**Quem usa:** tela de perdas (fila e criação de ordens), agente de IA.
**Responde a:** P6 (fila ordenada, motivo e energia a recuperar) e P7 (origem das ordens, que ficam no backend; Parte C).
**Grão:** 1 linha = 1 UC suspeita.
**Fontes:** `dim_uc` (Gold; as médias de consumo de 12 meses já vêm nela); inspecoes (Silver).

**Colunas** (estrutura fechada; a regra do `score` pode mudar de versão sem mudar as colunas):
- `id_uc` | texto | UC suspeita
- `prioridade` | inteiro | posição na fila (1 = mais promissora)
- `score` | decimal | pontuação de suspeita (0 a 100)
- `motivo` | texto | motivo legível (ex.: "consumo caiu 60% vs. 12 meses anteriores; medidor eletromecânico com 22 anos")
- `kwh_estimado_recuperar_mes` | decimal | `max(0, consumo médio dos 12 meses anteriores − consumo médio dos últimos 12)`, por mês; zero se a queda é explicada por GD
- `queda_consumo_pct` | decimal | queda vs. histórico da própria UC
- `consumo_vs_pares_pct` | decimal | consumo vs. UCs da mesma classe e do mesmo município + bairro
- `tipo_medidor` | texto | tipo do medidor ativo
- `idade_medidor_anos` | decimal | idade do medidor ativo
- `possui_gd` | booleano | UC tem GD
- `queda_explicada_por_gd` | booleano | UC com GD conectada a partir de `2024-07-01` e com queda de consumo (aproximação de "a queda começou depois da conexão"); rebaixa a UC
- `energia_injetada_atipica` | booleano | sinal da Silver de GD (log G5)
- `qtd_inspecoes_anteriores` | inteiro | inspeções já feitas na UC (0 se nunca inspecionada)
- `resultado_ultima_inspecao` | texto | `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE` (nulo se nunca inspecionada)
- `data_ultima_inspecao` | data | data da última inspeção (`data_inspecao` da Silver; nulo se nunca inspecionada)
- `municipio` | texto | município
- `bairro` | texto | bairro
- `classe` | texto | classe
- `data_referencia_score` | data | data dos dados usados no cálculo (fim da base)
- `versao_regra_score` | texto | versão da regra (ex.: `v1`), para rastrear mudanças na priorização

**O que a Silver de inspeções trouxe:**
- 1.389 inspeções, de agosto a dezembro de 2025, com o `resultado` padronizado em 2 valores (log I3).
- **Taxa de acerto histórica: 62,7%** (871 de 1.389), compatível com o "pouco mais da metade" do Rafael. É a referência para validar a regra: as UCs no topo da fila que já foram inspecionadas devem ter taxa de acerto **acima** de 62,7%.
- Em toda inspeção confirmada há tipo de irregularidade e energia recuperada positiva (mediana ~1.072 kWh). Essa energia é a referência de ordem de grandeza para `kwh_estimado_recuperar_mes`.

**Regra v1, implementada** (parâmetros na seção 2 do notebook; mudar a regra não muda o contrato, só o `versao_regra_score`). Pontos: queda de consumo da própria UC até 60 (de 10% a 40% de queda); medidor eletromecânico 15; medidor com 15 anos ou mais 5; consumo abaixo dos pares até 15; GD com injeção atípica 5. Ajustes: queda explicada por GD × 0,25; última inspeção sem irregularidade × 0,5; reincidência + 5. Corte da fila: score 40. **Validação retrospectiva:** score de 60 ou mais, 91,4% de irregularidade confirmada nas inspeções, contra 8,4% abaixo de 40 (referência: 62,7%). Os pesos vieram da análise dos quatro bairros, que usa as mesmas inspeções, então a validação não é independente.

O que a proposta original previa:
- **Energia a recuperar:** `max(0, consumo_medio_12m_anterior_kwh − consumo_medio_12m_kwh)` da `dim_uc`; **zero** quando `queda_explicada_por_gd = true`.
- **Sinais do score:** queda de consumo da própria UC; consumo abaixo dos pares (mesma classe, município + bairro); medidor eletromecânico ou antigo; `energia_injetada_atipica`.
- **Cuidados:** a GD derruba o consumo faturado em ~70% depois da conexão. Sem tratar isso, as 3.510 UCs com painel solar viram falsos suspeitos. Uma inspeção recente `SEM IRREGULARIDADE` rebaixa a UC; uma `IRREGULARIDADE CONFIRMADA` antiga pode subir a prioridade (reincidência).

**UC com ordem já aberta:** vem do banco do backend (Parte C), e não da Gold.

---

# Parte C — Fora da Gold (banco do backend)

A Gold é reconstruída pelo pipeline a cada execução. Dados **criados ou alterados no portal** se perderiam numa nova carga, então ficam em tabelas operacionais do backend (responsabilidade de Dev). Os campos abaixo são sugestões dos documentos de Dev e IA.

| Tabela operacional | Para quê | Campos sugeridos |
|---|---|---|
| `ordens_inspecao` | Criar, acompanhar e cancelar ordens a partir da fila (P7) | `id_ordem`, `id_uc`, `status`, `criada_em`, `atualizada_em`, `prioridade_original`, `motivo_suspeita`, `kwh_estimado_recuperar_mes`, `motivo_cancelamento` |
| `resultados_inspecao` | Registrar o resultado de campo (P7), inclusive por upload da planilha | `id_resultado`, `id_ordem`, `data_inspecao`, `resultado`, `observacoes`, `registrado_em` |
| `uso_providers_ia` | Registro das chamadas aos modelos de IA (hoje em JSON local) | `provider`, `model`, `timestamp`, `success`, `latency`, `error_type` |

**Resultado das inspeções novas:** para a fila poder usar as inspeções registradas no portal, `resultados_inspecao.resultado` deve usar os **mesmos 2 valores** da Silver: `IRREGULARIDADE CONFIRMADA` e `SEM IRREGULARIDADE`.

**Regras para o agente de IA:**
- Acesso **somente de leitura** às tabelas da Gold; o SQL gerado é validado antes de executar.
- O catálogo de métricas do agente é o **dicionário de dados** (P13): cada consulta respeita o grão e o período da tabela.
- Os insights recebem **valores já calculados**, com período e fonte identificados, e não apresentam hipóteses como causas comprovadas.

---

## Decisões

### Decididas
- **Receita = `valor_energia`.** `valor_energia` e `valor_total` dão a mesma variação de +8%, então a escolha não muda o diagnóstico.
- **Bandeira:** sem valor separado nas faturas; efeito estimado pelo preço por kWh (A4).
- **Inadimplência:** por competência e por faixa de atraso, nunca como um número único que misture anos. `dias_atraso` não mede inadimplência.
- **"Número de UCs":** sempre cadastradas ou faturadas, com a definição na coluna.
- **GD no mês (v4):** o mês da conexão conta; a mesma regra em A2, A3, A4 e A5.
- **Faturas em aberto antigas (v4):** a Gold guarda todas; a visão 360 filtra por `faixa_atraso` (como mostrar é decisão de Dev).
- **Períodos livres** na tela de receita e **filtros regionais** no dashboard: pela `fato_segmento_mensal` (A3).
- **DEC/FEC:** denominador por alimentador e mês; grade completa com zeros; DEC sempre mostrado com o número de UCs e as horas.
- **Causas evitáveis:** `VEGETACAO`, `FALHA DE EQUIPAMENTO` e `SOBRECARGA`.
- **Datas com horário** em interrupções e atendimentos (sem cast para data na Gold).
- **Atendimento (v4):** escala da nota de 1 a 5; tratativas fora da Gold; `ultima_acao` não é status.
- **Fila de inspeção (v4):** estrutura fechada; resultado em 2 valores; taxa de acerto de 62,7% como referência.
- **`fato_troca_medidor`** entra no escopo.
- **Variação de consumo por UC** na `dim_uc`.
- **Chave `id_uc`**, sem chave substituta na `dim_uc`.
- **Ordens, resultados de inspeção e uso de IA** ficam fora da Gold (Parte C).
- **UCs repetidas e as 200 UCs de teste:** resolvidas na Silver (U2, U3). Base de 45.000 UCs.
- **Máscara LGPD (v5):** primeiro nome + inicial dos sobrenomes; só os dígitos do meio do CPF ou CNPJ. As colunas originais não entram na Gold.
- **`OSCILACAO` no DEC/FEC (v5):** mantida (o glossário diz que cada registro é uma UC interrompida); suposição registrada no README.
- **Causa nula (v5):** não evitável; as horas evitáveis são um piso.
- **Regra do score v1 (v5):** implementada e validada retrospectivamente (B2).

### Em aberto
1. **Insights embutidos (IA):** a proposta de Dev é a tela de receita, com base na A3 e na A4. Confirmar com IA.

---

## Itens para o dicionário de dados

Decisões que afetam métricas. **Já estão no [dicionário de dados](dicionario_dados/README.md)** (P13), um arquivo por tabela:
- **Base de UCs = 45.000.** 200 registros de teste removidos; 1.260 linhas repetidas unificadas (U2, U3).
- **Bairros:** 297 pares município + bairro (272 nomes); bairro sempre junto com o município.
- **Receita = `valor_energia`**, que inclui o adicional de bandeira e exclui tributos. As 32.285 faturas órfãs (1,5% da receita) ficaram fora (F2).
- **Consumo no mês de troca de medidor** (6.299 linhas) = leitura atual do medidor novo (L5). Essa regra reproduz o −4% de volume do diretor; o preço por kWh desses meses fica ~5% acima do típico.
- **Faturas em aberto:** 172.553 (8,0%), em todos os anos desde 2022; 93% delas estão em `MAIS DE 90 DIAS`. `dias_atraso` de uma fatura em aberto conta até 2026-06-30; a inadimplência é por competência.
- **Atraso das pagas:** 83% das faturas pagas têm algum atraso (média de 10,8 dias; máximo de 25). Não confundir com inadimplência.
- **Variação contra o ano anterior:** nula em todo o primeiro ano da base.
- **GD no mês:** inclui o mês da conexão, que costuma ter GD só em parte.
- **Efeito da bandeira:** estimado, não medido.
- **GD:** 35 potências convertidas de watts (G2); 109 UCs com energia injetada atípica, sem uso como medida (G5).
- **`data_ligacao_estimada`:** 90 UCs com a data de instalação do 1º medidor (U9).
- **DEC/FEC simplificados:** cada ocorrência = 1 UC interrompida; servem para comparar alimentadores e períodos, não para comparar com os limites da ANEEL. 5.400 ocorrências sem causa informada entram no DEC/FEC (O1); 16.200 durações corrigidas (O2).
- **Atendimentos:** 9.566 chamados sem nota (3,0%), fora da média; acúmulo de notas em 5,0 como hipótese (A2); pico de julho de 2025 com 18.061 chamados (A6); `ultima_acao` não é a situação do chamado (A5); nenhum chamado aberto nesta base (A7).
- **Inspeções:** taxa de acerto de 62,7%; `NADA CONSTA` tratado como sem irregularidade (I3); 107 datas lançadas na aba de dezembro, mas de agosto a novembro (I2).

---

## Cobertura das perguntas

| Pergunta | Tabelas | Situação |
|---|---|---|
| P1. Por que volume −4% e receita +8%? | A4, A3, A5, A2, A1, A6 | ✅ Coberta: números do diretor reproduzidos na A2; a GD explica a queda de volume; bandeira estimada |
| P2. Preço × volume por município, bairro e classe | A4 (períodos do diagnóstico), A3 (qualquer período) | ✅ Coberta |
| P3. Indicadores e comparação entre períodos | A5 (empresa), A3 (por segmento) | ✅ Coberta |
| P4. Visão 360 | A1, A2, A7, B1 | ✅ Coberta |
| P5. Conta alta: o consumo subiu? | A2, A6 | ✅ Coberta |
| P6. Fila de suspeitas | B2 | ✅ Coberta: regra v1 implementada e validada retrospectivamente |
| P7. Ordens de inspeção | Parte C | ➖ Responsabilidade de Dev; a Gold entrega a fila |
| P8. DEC/FEC por alimentador | A8 | ✅ Coberta |
| P9. Regiões e manutenção preventiva | A8, A7 | ✅ Coberta (horas por causa evitável e por local) |
| P10. Agente de IA | todas | ✅ Coberta para consumo, faturamento, interrupções e atendimento |
| P11. Insights embutidos | A3, A4, A5 | ⚠️ Confirmar a tela com IA |
| P12. Filtros | A3 e colunas de município, bairro e classe nas fatos | ✅ Coberta |
| P13. Dicionário de dados | — | ✅ Coberta: [`docs/dicionario_dados/`](dicionario_dados/README.md), um arquivo por tabela |

**Validação com números do case:** 45.000 UCs ✅, 14 municípios ✅, 122 alimentadores (case: "mais de 120") ✅, volume −3,95% (case: "quase 4%") ✅, receita +8% ✅, 297 bairros (case: "quase 300") ✅, ~1,4 mil inspeções (1.389) ✅, taxa de acerto "pouco mais da metade" (62,7%) ✅.

---

## Como os comentários de Dev e IA entraram

| Comentário | Origem | Como ficou |
|---|---|---|
| `kpis_mensal` não permite filtros regionais | Dev (dashboard) | Nova `fato_segmento_mensal` (A3) |
| Definir o que é "número de UCs" | Dev (dashboard) | Convenção: cadastradas ou faturadas, nas duas colunas |
| `receita_decomposicao` só tem os períodos fixos | Dev (receita) | A4 fica para o diagnóstico; períodos livres pela A3 + fórmulas da A4 |
| Tratar grupos com volume zero | Dev (receita) | Regra na A4 |
| Preservar data e hora em interrupções e atendimentos | Dev (visão 360) | `data_hora_*` na A7 e na B1 |
| Denominador do DEC por alimentador e mês | Dev (qualidade) | `qtd_ucs_alimentador_mes` (A8) |
| Meses sem interrupção com DEC/FEC zero | Dev (qualidade) | Grade completa na A8 |
| Análise por causa | Dev (qualidade) | `causa` e `causa_evitavel` na A7; horas evitáveis na A8 |
| Não atribuir DEC do alimentador ao bairro | Dev (qualidade) | Nota na A8 |
| Fórmula do score e da energia a recuperar | Dev (perdas) | Regra v1 na B2, implementada e validada |
| `data_referencia_score` e `versao_regra_score` | Dev (perdas) | Colunas na B2 |
| Ordens e resultados fora da Gold | Dev (perdas) | Parte C; resultado com os mesmos 2 valores da Silver |
| Agente só de leitura, catálogo de métricas, SQL validado | Dev (chat) e IA | Parte C |
| Insights com valores calculados, sem tratar hipótese como causa | Dev (insights) | Parte C |
| Uso dos modelos de IA no banco | IA (fallback e quotas) | `uso_providers_ia` na Parte C |
