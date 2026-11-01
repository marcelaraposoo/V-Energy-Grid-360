# Backend — V-Energy Grid 360 (FastAPI)

API do portal. Roda com **dados mockados** (`DATA_SOURCE=mock`, o padrão) ou com a Gold local
(`DATA_SOURCE=sqlite`). A leitura das tabelas necessárias à Visão 360 está implementada;
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
| GET | `/receita/variacao?agrupar_por=municipio\|bairro\|classe` | efeito preço × volume (drill-down) |
| GET | `/unidades?q=`, `/unidades/{uc}/visao-360` | atendente |
| GET | `/unidades/{uc}/faturas?aba=recentes\|historico&pagina=1` | faturas paginadas, com resumo de pendências e filtros de ano/situação no histórico |
| GET | `/perdas/fila?q=&pagina=&tamanho=` | fila priorizada, com busca e paginação (total no cabeçalho `X-Total-Count`) |
| GET | `/perdas/fila/exportar?q=&municipio=&classe=&prob_minima=&limite=` | fila filtrada em CSV (`;`, UTF-8 com BOM, abre no Excel); `limite` padrão 500, máximo 5000 |
| POST/GET | `/perdas/ordens`, `/{id}/iniciar`, `/{id}/resultado`, `/{id}/cancelar` | ordens de inspeção |
| GET | `/continuidade/alimentadores`, `/alimentadores/{id}/serie` | DEC/FEC |
| POST/GET | `/ia/perguntar` (stub), `/ia/insights?tela=` | módulo de IA |

Filtros comuns: `municipio`, `bairro`, `classe`; períodos: `base_inicio/base_fim/atual_inicio/atual_fim` (`YYYY-MM`).
Padrão: base = primeiros 12 meses, atual = últimos 12 (como na pergunta do diretor).

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
Os gráficos do frontend continuam com os mocks de apresentação até a etapa de integração.

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
Os demais KPIs mantêm seus cálculos anteriores; a homologação da exportação oficial é pendente.

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
