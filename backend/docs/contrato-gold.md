# Mapeamento da Gold v4 para o backend

A fonte principal é o contrato consolidado da **Gold v4**, fornecido pela frente de Dados.
Este documento registra como o backend consome essa fonte; não redefine o
contrato. Em caso de divergência, prevalece o contrato consolidado.

O adaptador [SQLite](../app/repositories/sqlite_repo.py) lê a Gold sem alterações no banco.
A chave da UC é `id_uc`; o mapeamento não pressupõe chaves substitutas `*_sk`.
Os modelos expostos ao frontend estão em [schemas.py](../app/schemas.py).

## Fontes e consumidores implementados

| Tabela Gold | Grão / finalidade | Consumo no portal |
|---|---|---|
| A1 `dim_uc` | Uma UC | Cadastro, busca, catálogos, medidor ativo e GD da Visão 360 |
| A2 `fato_consumo_faturamento` | UC × competência | Consumo e faturas da Visão 360, paginação e diagnóstico de conta alta |
| A3 `fato_segmento_mensal` | Competência × município × bairro × classe | KPIs e série com filtros regionais; faturamento em aberto e consumo por classe na visão geral |
| A5 `kpis_mensal` | Uma competência | KPIs e série da visão geral; posição final de UCs cadastradas, faturadas e com GD |
| A6 `fato_troca_medidor` | Evento de troca | Histórico de trocas da UC |
| A7 `fato_interrupcao` | Evento de interrupção | Ocorrências e contexto da UC/alimentador |
| A8 `dec_fec_alimentador_mensal` | Alimentador × competência | Indicadores de continuidade; KPIs padrão de DEC/FEC |
| B1 `fato_atendimento` | Atendimento | Histórico e detalhes de atendimentos da UC |
| B2 `fila_inspecao` | UC priorizada | Fila de inspeção e motivos de suspeita |

A leitura dessas fontes está implementada, mas depende das tabelas e colunas necessárias
na exportação configurada. A Análise da Receita calcula a decomposição preço × volume pela A3
`fato_segmento_mensal`, para qualquer par de períodos de mesma duração e sem sobreposição. O fator
GD compara as mesmas UCs nos dois períodos (as que têm GD no fim do período atual, regra da A4) e,
por isso, vem da A2 `fato_consumo_faturamento`, que tem o grão por UC; sem a A2 exportada, os dois
volumes de GD voltam nulos e o restante da tela funciona. A A4 `receita_decomposicao` não é lida
pela tela. A consulta global `faturas(...)` continua devolvendo 501 no adaptador SQLite e não é
mais usada pela Receita. `tests/manual/validar_receita_gold.py` confere a A3 contra a A2 e os
números do diagnóstico no `gold.db` real.

## Dashboard Executivo

O Dashboard já consulta a API para todos os seus cards e gráficos. A interface mantém somente
filtros temporais; filtros por município, bairro e classe continuam disponíveis nos endpoints
que os suportam e nas demais funcionalidades. As rotas e respostas estão detalhadas no
[README do backend](../README.md#períodos-e-kpis-do-dashboard).

| Indicador | Fonte / regra |
|---|---|
| Receita de energia | Soma de `receita_energia`, sem tributos, nas competências selecionadas |
| Consumo faturado | Soma do consumo mensal nas competências selecionadas |
| Preço médio por kWh | Soma da receita de energia / soma do consumo, sem média simples de taxas |
| UCs faturadas | Posição da última competência; preservada na API, mesmo sem card na tela |
| Faturamento em aberto | A3: `SUM(valor_em_aberto) / SUM(receita_total) * 100` |
| UCs cadastradas e GD | A5: `qtd_ucs_cadastradas` e `qtd_ucs_com_gd` da última competência |
| Consumo por classe | A3: soma de `consumo_kwh` por classe em cada intervalo |

Na visão geral, os três primeiros indicadores e UCs faturadas usam a A5; nas consultas com
filtros regionais, usam a A3 agregada por competência. A seleção `indicador=executivo` evita
dependência da A8 e preserva UCs faturadas na resposta.

O consolidado de faturamento em aberto é uma regra derivada da API para o intervalo solicitado,
aplicando a definição monetária da Gold, não uma nova coluna da A5. Soma os segmentos antes
da divisão e usa `receita_total`, incluindo tributos, como denominador. Considera todas as
faturas ainda em aberto na data de corte **30/06/2026**, inclusive não vencidas, preservando
a competência original. Não usa `dias_atraso` de faturas pagas. A diferença entre taxas é
em pontos percentuais; a taxa da última competência é apresentada separadamente, sem segunda variação.

Os gráficos de evolução usam valores mensais, sem acumulação progressiva. Contagens de UCs
não são somadas entre competências. A participação de GD é `qtd_ucs_com_gd / qtd_ucs_cadastradas * 100`.

### Completude e agregação

- As competências são mensais (`YYYY-MM`), de jul/2022 a jun/2026 na base do case.
  A duração dos intervalos é inclusiva, sem contagem por dias.
- Competências ausentes não são substituídas por outros meses nem preenchidas com zero.
  Um consolidado incompleto fica indisponível; a última competência pode continuar válida.
- Na A3, existem apenas as combinações presentes na base. Por decisão de implementação,
  uma classe sem registro em algum mês selecionado tem seu consolidado indisponível,
  pois a ausência sozinha não distingue consumo zero de dados faltantes. Um total incompleto
  também impede calcular as participações das classes.
- Zeros registrados são preservados. Denominador zero ou inválido não produz percentual;
  referência zero ou ausente não produz variação percentual relativa.
- Duplicações no grão da agregada são reportadas em vez de somadas duas vezes.
  Município e bairro compõem o recorte; bairro isolado não deve identificar um segmento.

## Mapeamento do cadastro

| Portal | `dim_uc` | Observação |
|---|---|---|
| `uc_id` | `id_uc` | Chave comum às fatos; busca ignora caixa |
| `titular` | `nome_titular_mascarado` | Expor somente o nome mascarado |
| `classe` | `classe` | RESIDENCIAL, COMERCIAL, INDUSTRIAL, PODER PUBLICO ou RURAL |
| `subgrupo_tarifario` | `subgrupo_tarifario` | Campo separado de classe: B1, B2, B3 ou A4 |
| `alimentador_id` | `alimentador` | Cadastro do alimentador derivado das UCs; município principal pelo maior número de UCs |
| `possui_gd` | `possui_gd` | Situação cadastral da UC |
| `medidor` | Campos do medidor ativo | Ausente quando a UC não possui medidor ativo |
| `geracao_distribuida` | Campos de GD da UC | Potência, conexão, modalidade e energia injetada; preservar a sinalização de energia atípica |

As quantidades mensais de GD do Dashboard vêm da A5, respeitando a competência de conexão;
não são reconstruídas a partir da posição cadastral atual da A1.

## Limites e validação pendente

- `DATA_SOURCE=mock` usa dados fictícios determinísticos; `DATA_SOURCE=sqlite` abre a
  exportação indicada por `SQLITE_PATH`, somente para leitura.
- Tabela ou coluna necessária ausente resulta em 501, com identificação no `detail`.
  Um registro mensal ausente em tabela existente é tratado como indisponibilidade do dado.
- Na fila, `score / 100` é adaptado ao campo `probabilidade` do portal; é uma escala de
  prioridade, não uma probabilidade estatística calibrada.
- `ordens_inspecao` pertence ao portal e fica no banco separado `data/portal.db`
  (configurável por `PORTAL_DB_PATH`). A exportação da Gold não armazena nem sobrescreve essas ordens.
- Os testes com mocks e SQLite sintético verificam os adaptadores e a API, mas não substituem
  a **homologação da exportação oficial**, que continua pendente. Divergências entre A3 e A5
  devem ser investigadas na fonte, sem correções silenciosas de valores no portal.
