# Backend — V-Energy Grid 360 (FastAPI)

API do portal. Roda com **dados mockados** (`DATA_SOURCE=mock`, o padrão) ou com a Gold local
(`DATA_SOURCE=sqlite`). A leitura das tabelas necessárias ao Dashboard e à Visão 360 está implementada;
a homologação com a exportação oficial continua pendente.

## Rodar
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Docs interativas: http://localhost:8000/docs · Testes: `pytest`

## Usar a Gold local
1. Coloque o `gold.db` exportado em `backend/data/` (ou aponte `SQLITE_PATH` no `.env`) e use `DATA_SOURCE=sqlite`.
2. O arquivo precisa ter `dim_uc`. Para a Visão 360 completa, também são necessárias
   `fato_consumo_faturamento`, `fato_troca_medidor`, `fato_interrupcao`,
   `dec_fec_alimentador_mensal` e `fato_atendimento`. O banco é aberto só para leitura.
3. As consultas por UC de cadastro, consumo, faturas paginadas, medidor, trocas, GD, interrupções,
   continuidade e atendimentos estão implementadas. Catálogos, busca e fila de inspeção também
   possuem leitura SQLite; a fila requer `fila_inspecao`.
4. Uma tabela necessária ausente devolve **501**, com a tabela no `detail`. Os KPIs e a série
   mensal do Dashboard usam as agregadas Gold. A consulta global de faturas da análise de
   receita ainda devolve 501 no SQLite. Veja o
   [mapeamento da Gold](docs/contrato-gold.md) para os limites de cada bloco.
5. As ordens de inspeção continuam em `data/portal.db`, nos dois modos.

## Estrutura
```
app/
  main.py            # app, CORS (front em :5173), handlers 404/409
  core/              # config (.env) e erros de domínio
  mock/              # gerador determinístico de dados fake
  repositories/      # contrato e adaptadores mock/SQLite; armazenamento separado das ordens
  services/          # regras de negócio (receita, dashboard, unidades, perdas, continuidade, ia)
  routers/           # endpoints finos que só chamam services
  schemas.py         # modelos Pydantic (contrato com o frontend)
tests/               # pytest
docs/contrato-gold.md
```

## Endpoints (`/api`)
| Método | Rota | Tela / user story |
|---|---|---|
| GET | `/filtros` | selects de filtros |
| GET | `/dashboard/kpis`, `/dashboard/serie` | visão do diretor |
| GET | `/dashboard/cadastro-gd` | UCs cadastradas e GD na última competência de cada período |
| GET | `/dashboard/consumo-classes` | consumo consolidado por classe, participação e comparação |
| GET | `/receita/variacao?agrupar_por=municipio\|bairro\|classe` | efeito preço × volume (drill-down) |
| GET | `/unidades?q=`, `/unidades/{uc}/visao-360` | atendente |
| GET | `/unidades/{uc}/faturas?aba=recentes\|historico&pagina=1` | faturas paginadas, com resumo de pendências e filtros de ano/situação no histórico |
| GET | `/perdas/fila?q=&pagina=&tamanho=` | fila priorizada, com busca e paginação (total no cabeçalho `X-Total-Count`) |
| GET | `/perdas/fila/exportar?q=&municipio=&classe=&prob_minima=&limite=` | fila filtrada em CSV (`;`, UTF-8 com BOM, abre no Excel); `limite` padrão 500, máximo 5000 |
| POST/GET | `/perdas/ordens`, `/{id}/iniciar`, `/{id}/resultado`, `/{id}/cancelar` | ordens de inspeção |
| GET | `/continuidade/alimentadores`, `/alimentadores/{id}/serie` | DEC/FEC |
| POST/GET | `/ia/perguntar` (stub), `/ia/insights?tela=` | módulo de IA |

Filtros comuns: `municipio`, `bairro`, `classe`; períodos: `base_inicio/base_fim/atual_inicio/atual_fim` (`YYYY-MM`).
O padrão da rota de KPIs sem parâmetros mantém base = primeiros 12 meses e atual = últimos
12 meses, com comparação (como na pergunta do diretor). O frontend inicia sem comparação e
envia isso explicitamente; não depende desse padrão da API.

### Períodos e KPIs do Dashboard

Os quatro endpoints do Dashboard aceitam `atual_inicio`, `atual_fim`, `base_inicio`,
`base_fim` e `comparar`. Os limites da base do case são jul/2022 a jun/2026, com duração
calculada em competências mensais inclusivas:

- `comparar=false`: de 1 a 24 meses, sem parâmetros `base_*` na consulta da tela e sem variações.
- Com comparação: mês × mês ou períodos de 2 a 12 meses cada, durações iguais e sem sobreposição.
  Não é necessário selecionar os mesmos meses do calendário.
- Períodos inválidos retornam 422 antes da leitura dos indicadores.

`GET /api/dashboard/kpis?indicador=executivo` retorna receita, consumo, preço médio,
UCs faturadas e inadimplência, sem depender da A8. O frontend reutiliza essa resposta para
os três KPIs principais e faturamento em aberto; UCs faturadas permanecem na API.
`indicador=inadimplencia` consulta somente esse indicador. Sem `indicador`, o contrato
mantém também DEC/FEC. Os nomes dos KPIs e campos da resposta são preservados.

Na visão geral, receita, consumo, preço e UCs faturadas usam a A5 (`kpis_mensal`).
Com filtros regionais ou de classe, usam a A3 (`fato_segmento_mensal`), agregada por mês.
Receita de energia e consumo são somados exclusivamente nos meses selecionados;
preço médio = soma de `receita_energia` / soma do consumo, sem média simples dos preços.
UCs faturadas usam a última competência, sem somar contagens mensais.

Uma competência ausente invalida os acumulados que dependem dela. Valores nulos permanecem
indisponíveis, zeros presentes são preservados, e denominador zero não produz uma razão.
Sem referência ou sem os valores necessários, a variação fica nula; uma referência zero
não produz variação percentual relativa. A homologação com a Gold oficial continua pendente.

### Cadastro e geração distribuída

`GET /api/dashboard/cadastro-gd` consulta exclusivamente a competência final de cada intervalo
na A5, usando `qtd_ucs_cadastradas` e `qtd_ucs_com_gd`. Não soma meses nem substitui uma
competência ausente. `percentual_gd = qtd_ucs_com_gd / qtd_ucs_cadastradas * 100`;
denominador zero ou valor indisponível resulta em percentual nulo.

`CadastroGdResponse` contém `atual`, `referencia` opcional e `variacao_cadastradas_pct`,
comparando as posições finais quando válidas. Essa rota é global, somente com filtros temporais.

### Consumo por classe

`GET /api/dashboard/consumo-classes` soma `consumo_kwh` da A3 por classe e intervalo.
Retorna RESIDENCIAL, COMERCIAL, INDUSTRIAL, PODER PUBLICO e RURAL em ordem decrescente
de volume principal, com indisponíveis ao final. Não aplica filtros regionais ou de classe.

- Participação: `consumo_classe / consumo_total * 100`.
- Variação: `(consumo_principal - consumo_referencia) / consumo_referencia * 100`.
- Ausência de uma classe em qualquer mês selecionado invalida seu volume consolidado;
  não é interpretada como zero. Se algum volume está indisponível, o total e as participações
  também ficam nulos. Um zero registrado continua válido; total zero não produz participação.
- Referência zero ou ausente não produz variação percentual. A resposta inclui os volumes
  de referência e listas de competências ausentes. Segmentos duplicados e classes desconhecidas
  são reportados, evitando agregações silenciosamente incorretas.

`ConsumoClassesResponse` fornece uma única série principal para as barras; o volume de
referência serve à variação e ao tooltip, sem exigir barras duplas.

### Série mensal do Dashboard

`GET /api/dashboard/serie` usa A5 (`kpis_mensal`) sem filtros e agrega A3
(`fato_segmento_mensal`) por competência quando há município, bairro ou classe.
Os campos da resposta permanecem `competencia`, `receita`, `energia_kwh` e `tarifa_media`.
Receita é a energia faturada, sem tributos; os pontos são mensais, sem acumulação progressiva.
O preço mensal divide a soma da receita pela soma do consumo, com quatro casas decimais.
Receita e consumo têm duas casas na resposta, como os KPIs principais.

Sem parâmetros temporais, retorna o histórico inteiro do catálogo (48 meses na base do case).
Com `atual_*`, `base_*` ou `comparar`, mantém as validações do Dashboard e retorna somente
os intervalos selecionados, em ordem cronológica e com as competências reais. A comparação
opcional consulta cada intervalo separadamente, sem ler meses entre eles.

Uma competência ausente mantém seu ponto com valores `null`; não é preenchida com zero
nem substituída por outro mês. Nulos de uma métrica preservam as demais quando disponíveis.
Zeros presentes são mantidos, e consumo zero torna `tarifa_media` nula. Uma agregada necessária
ausente continua retornando 501. A consulta não depende de faturas globais nem da A8.
Os gráficos do frontend já consomem essa série pela API. A fonte continua sendo mock ou SQLite,
conforme `DATA_SOURCE`; a integração da tela não equivale à homologação da exportação oficial.

### Faturamento em aberto no Dashboard

O KPI `Inadimplência` usa a A3 (`fato_segmento_mensal`), inclusive na visão geral:
`SUM(valor_em_aberto) / SUM(receita_total) * 100`. O denominador inclui tributos.
A consulta preserva as competências selecionadas e a situação conhecida até 30/06/2026;
inclui todas as faturas em aberto, mesmo ainda não vencidas, sem usar `dias_atraso`.
Esse consolidado é derivado para o intervalo solicitado; não substitui o indicador mensal da A5.

- `valor_atual`/`valor_base`: taxas consolidadas, ou `null` quando indisponíveis.
- `variacao_pp`: principal menos referência, em pontos percentuais; `variacao_pct` e
  `variacao_abs` ficam nulos para inadimplência. Sem referência, não há variação.
- `inadimplencia`: taxa da última competência, competências ausentes de cada intervalo
  e `data_corte`. A taxa final não recebe uma segunda comparação.

Uma competência ausente invalida o consolidado inteiro, preservando a taxa final quando
disponível. Valores monetários nulos, não finitos ou negativos invalidam a razão afetada;
denominador zero não produz uma taxa. Registros presentes com zero não são lacunas.
Segmentos duplicados são reportados em vez de agregados duas vezes.
Para um único mês, a tela apresenta apenas a taxa mensal. Em vários meses, destaca o consolidado
e mostra a última competência como informação secundária. Os cálculos dos outros indicadores
seguem as fontes descritas acima; a homologação da exportação oficial é pendente.

### Diagnóstico de conta alta

`GET /api/unidades/{uc}/visao-360` aceita `competencia_atual` e `competencia_referencia`
em `YYYY-MM`. O padrão é a última competência disponível da UC × a competência anterior
disponível. A referência deve ser anterior ao mês analisado; os seletores mostram somente
meses com histórico. Exemplo:

`/api/unidades/UC000001/visao-360?competencia_atual=2026-06&competencia_referencia=2025-06`

A resposta identifica as competências e separa totais, percentuais e classificações de consumo (kWh)
e faturamento (`valor_total`, R$). Dados ausentes e referência zero têm mensagens próprias.
Os limites das faixas ficam nas constantes `LIMITE_VARIACAO_PEQUENA_PCT` e
`LIMITE_VARIACAO_MODERADA_PCT`, em `app/services/unidades.py`. O histórico geral não depende desse filtro.

### Outros blocos da Visão 360

- `faturas` contém a última fatura; a listagem consulta a rota paginada, com 10 registros por página.
  `resumo_faturas` considera todas as competências da UC, independentemente dos filtros.
- `trocas_medidor` preserva as 13 colunas da A6. As médias excluem o mês da troca;
  gráfico e diagnóstico sinalizam a competência usando a flag da A2, sem inferir causalidade.
- `periodo_interrupcoes=6_meses|12_meses|todos` atualiza ocorrências da UC e contexto do
  alimentador; o padrão é 12 meses. DEC/FEC usam os indicadores mensais da A8.
- A API mantém `periodo_atendimentos=6_meses|12_meses|todos`, padrão 12 meses. A tela
  solicita `todos` e aplica situação, contagens e paginação no frontend.

## Premissas
- Mock: 400 UCs, 48 competências (2022-07 a 2026-06); ordens de inspeção ficam no SQLite do portal (`data/portal.db`, criado sozinho) e sobrevivem a reinícios. Para zerar, pare o servidor e apague o arquivo. O caminho muda com `PORTAL_DB_PATH` no `.env`.
- Efeito-preço inclui reajuste + bandeira + mix de classes.
- Na Visão 360, DEC/FEC descrevem o alimentador; a quantidade e a duração do histórico descrevem a própria UC. A base mensal de UCs e o impacto em UC × horas acompanham os indicadores.
- UC com ordem ativa sai da fila de suspeitas; score de prioridade = probabilidade × kWh/mês recuperável.
