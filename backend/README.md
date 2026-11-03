# Backend — V-Energy Grid 360 (FastAPI)

API do portal V-Energy Grid 360, responsável por disponibilizar os dados e indicadores utilizados pelo frontend, incluindo Dashboard, Visão 360, análise de receita, perdas, continuidade e recursos de IA.

O backend pode operar com dados mockados (`DATA_SOURCE=mock`, padrão) ou com a Gold local (`DATA_SOURCE=sqlite`). A integração com SQLite contempla as consultas descritas neste documento.

A execução local com a Gold atualizada foi validada. A reprodução do processo de exportação oficial deve seguir as instruções e os procedimentos disponibilizados pela equipe de DADOS.

## Sumário

- [Requisitos](#requisitos)
- [Como executar](#como-executar)
- [Configuração da Gold local](#configuração-da-gold-local)
- [Estrutura do backend](#estrutura-do-backend)
- [Endpoints da API](#endpoints-da-api)
- [Períodos e KPIs do Dashboard](#períodos-e-kpis-do-dashboard)
- [Cadastro e geração distribuída](#cadastro-e-geração-distribuída)
- [Consumo por classe](#consumo-por-classe)
- [Série mensal do Dashboard](#série-mensal-do-dashboard)
- [Faturamento em aberto no Dashboard](#faturamento-em-aberto-no-dashboard)
- [Diagnóstico de conta alta](#diagnóstico-de-conta-alta)
- [Outros blocos da Visão 360](#outros-blocos-da-visão-360)
- [Testes e validação](#testes-e-validação)
- [Premissas e limitações](#premissas-e-limitações)

## Requisitos

- Python compatível com as dependências declaradas em `requirements.txt`.
- Git para obter o código-fonte.
- Gold `gold.db` disponibilizada pela equipe de DADOS, caso a execução seja feita com SQLite.
- Node.js e npm para executar o frontend, documentado separadamente no README principal do projeto.

## Como executar

### 1. Preparar o ambiente

Na raiz do repositório, entre na pasta do backend:

```bash
cd backend
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**Linux/macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Se o arquivo `.env` já existir, revise-o em vez de sobrescrevê-lo.

### 2. Configurar a fonte de dados

No arquivo `backend/.env`, defina a fonte desejada:

```dotenv
DATA_SOURCE=mock
```

Para executar com os dados mockados, mantenha `DATA_SOURCE=mock`.

Para utilizar a Gold local, configure:

```dotenv
DATA_SOURCE=sqlite
```

A configuração `DATA_SOURCE=mock` é o padrão quando nenhuma configuração diferente é fornecida. O backend seleciona o repositório correspondente à fonte configurada.

**Importante:** o arquivo `.env` é local e não deve ser enviado ao Git. Não compartilhe credenciais ou outros dados sensíveis presentes em arquivos de configuração.

### 3. Iniciar o servidor

Execute o comando a partir da pasta `backend`, com o ambiente virtual ativado:

```bash
uvicorn app.main:app --reload --port 8000
```

A API estará disponível em:

- API: `http://localhost:8000`
- Documentação interativa: `http://localhost:8000/docs`
- Documentação alternativa: `http://localhost:8000/redoc`

O frontend de desenvolvimento utiliza normalmente `http://localhost:5173`.

## Configuração da Gold local

### 1. Obter o banco de dados

Obtenha a versão da Gold disponibilizada pela equipe de DADOS, seguindo o procedimento oficial de exportação do projeto.

O arquivo `gold.db` não é versionado no Git. Cada desenvolvedor deve obter o artefato disponibilizado pela equipe e verificar se está utilizando a versão esperada.

### 2. Posicionar o arquivo

O caminho padrão esperado para o banco do backend é:

```text
backend/
├── data/
│   ├── gold.db
│   └── portal.db
├── app/
├── tests/
├── .env
└── requirements.txt
```

Coloque a Gold em `backend/data/gold.db`. Caso utilize outro caminho, configure `SQLITE_PATH` conforme a implementação de configuração do backend.

Não substitua nem exclua `portal.db` ao atualizar a Gold: esse arquivo possui finalidade diferente.

### 3. Tabelas necessárias

A Gold recebida contém as seguintes dez tabelas funcionais:

| Tabela | Finalidade geral |
|---|---|
| `dim_uc` | Cadastro e dimensões das unidades consumidoras |
| `fato_consumo_faturamento` | Consumo e faturamento por UC e competência |
| `fato_atendimento` | Registros de atendimentos |
| `receita_decomposicao` | Componentes utilizados na análise de receita |
| `fato_segmento_mensal` | Indicadores agregados por segmento e competência |
| `kpis_mensal` | Indicadores consolidados por competência |
| `fato_troca_medidor` | Histórico de trocas de medidores |
| `fato_interrupcao` | Ocorrências de interrupção |
| `dec_fec_alimentador_mensal` | Indicadores de continuidade por alimentador |
| `fila_inspecao` | Unidades priorizadas para inspeção |

A tabela interna `sqlite_stat1`, quando presente, é utilizada pelo SQLite para estatísticas de otimização e não constitui uma tabela funcional adicional da Gold.

A presença de uma tabela no banco não garante, isoladamente, que todos os campos e registros necessários estejam disponíveis. O contrato de cada bloco deve ser consultado em [`docs/contrato-gold.md`](docs/contrato-gold.md).

### 4. Leitura e limitações

O repositório SQLite da Gold utiliza o banco para leitura. As ordens de inspeção são armazenadas separadamente no banco do portal.

As consultas implementadas abrangem:

- Cadastro e pesquisa de UCs.
- Consumo, faturamento e faturas paginadas por UC.
- Dados de medidores e trocas.
- Geração distribuída.
- Interrupções e continuidade.
- Atendimentos.
- Catálogos e fila de inspeção.
- Indicadores e séries do Dashboard.

A disponibilidade de cada bloco depende das tabelas, colunas e dados exigidos pelo respectivo contrato.

Quando uma tabela necessária não está disponível, determinados endpoints retornam HTTP `501`, com detalhes sobre a dependência ausente. A consulta global de faturas da análise de receita permanece limitada no modo SQLite.

Para detalhes sobre as fontes, tabelas, colunas e limitações de cada bloco, consulte [`docs/contrato-gold.md`](docs/contrato-gold.md).

### 5. Banco do portal

As ordens de inspeção são mantidas em `backend/data/portal.db`, ou no caminho definido por `PORTAL_DB_PATH`.

Esse banco é separado da Gold e pode ser utilizado nos modos mock e SQLite. Ele armazena dados operacionais do portal, como ordens de inspeção, enquanto a Gold contém os dados analíticos.

**Atenção:** o script de exportação da Gold recria o banco Gold. Não utilize esse procedimento para recriar o banco do portal, pois são arquivos com finalidades distintas.

## Estrutura do backend

```text
backend/
├── app/
│   ├── main.py             # Aplicação FastAPI, CORS e handlers HTTP
│   ├── core/               # Configuração e erros de domínio
│   ├── mock/               # Gerador determinístico de dados mockados
│   ├── repositories/       # Contratos e adaptadores mock/SQLite
│   ├── services/           # Regras de negócio e cálculos
│   ├── routers/            # Endpoints da API
│   └── schemas.py          # Modelos Pydantic e contratos com o frontend
├── data/
│   ├── gold.db             # Gold local, obtida externamente
│   └── portal.db           # Persistência operacional do portal
├── docs/
│   └── contrato-gold.md    # Mapeamento e limitações da integração com a Gold
├── tests/                  # Testes automatizados com pytest
├── .env.example            # Exemplo de configuração
└── requirements.txt        # Dependências Python
```

A organização separa as rotas HTTP, as regras de negócio, os modelos de dados e os adaptadores de persistência.

## Endpoints da API

As rotas abaixo são disponibilizadas sob o prefixo `/api`, salvo indicação em contrário.

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/api/filtros` | Opções para os filtros da aplicação |
| GET | `/api/dashboard/kpis` | Indicadores consolidados do Dashboard |
| GET | `/api/dashboard/serie` | Série mensal do Dashboard |
| GET | `/api/dashboard/cadastro-gd` | UCs cadastradas e geração distribuída |
| GET | `/api/dashboard/consumo-classes` | Consumo por classe, participação e comparação |
| GET | `/api/receita/variacao?agrupar_por=municipio` | Análise de variação de receita com agrupamento |
| GET | `/api/unidades?q=` | Pesquisa de unidades consumidoras |
| GET | `/api/unidades/{uc}/visao-360` | Visão 360 da UC |
| GET | `/api/unidades/{uc}/faturas?aba=recentes&pagina=1` | Faturas paginadas |
| GET | `/api/perdas/fila?q=&pagina=&tamanho=` | Fila priorizada, com busca e paginação |
| GET | `/api/perdas/fila/exportar?q=&municipio=&classe=&prob_minima=&limite=` | Exportação da fila filtrada em CSV |
| GET/POST | `/api/perdas/ordens` | Consulta e criação de ordens de inspeção |
| POST | `/api/perdas/ordens/{id}/iniciar` | Início de uma ordem |
| POST | `/api/perdas/ordens/{id}/resultado` | Registro do resultado de uma ordem |
| POST | `/api/perdas/ordens/{id}/cancelar` | Cancelamento de uma ordem |
| GET | `/api/continuidade/alimentadores` | Indicadores de continuidade por alimentador |
| GET | `/api/alimentadores/{id}/serie` | Série de continuidade do alimentador |
| POST | `/api/ia/perguntar` | Interface de perguntas do módulo de IA, atualmente identificada como stub |
| GET | `/api/ia/insights?tela=` | Insights associados à tela |

Os parâmetros e contratos específicos devem ser consultados na documentação interativa em `/docs`.

### Filtros comuns

Os filtros regionais mais utilizados são `municipio`, `bairro` e `classe`.

Os parâmetros de período são:

- `base_inicio`
- `base_fim`
- `atual_inicio`
- `atual_fim`

Os períodos utilizam o formato `YYYY-MM`.

A rota de KPIs, quando chamada sem parâmetros, mantém como padrão a base formada pelos primeiros 12 meses e o período atual formado pelos últimos 12 meses, com comparação. O frontend pode desabilitar a comparação e envia essa escolha explicitamente.

## Períodos e KPIs do Dashboard

Os quatro endpoints do Dashboard aceitam `atual_inicio`, `atual_fim`, `base_inicio`, `base_fim` e `comparar`.

Os limites da base do case são julho de 2022 a junho de 2026. A duração dos intervalos é calculada por competências mensais inclusivas.

- `comparar=false`: períodos de 1 a 24 meses, sem parâmetros `base_*` na consulta da tela e sem variações.
- Com comparação: mês × mês ou períodos de 2 a 12 meses cada, com durações iguais e sem sobreposição.
- Não é necessário selecionar os mesmos meses do calendário.
- Períodos inválidos retornam HTTP `422` antes da leitura dos indicadores.

`GET /api/dashboard/kpis?indicador=executivo` retorna receita, consumo, preço médio, UCs faturadas e inadimplência, sem depender da A8. O frontend reutiliza essa resposta para os três KPIs principais e o faturamento em aberto; UCs faturadas permanecem disponíveis na API.

`indicador=inadimplencia` consulta somente esse indicador. Sem `indicador`, o contrato mantém também DEC/FEC. Os nomes dos KPIs e os campos da resposta são preservados.

Na visão geral, receita, consumo, preço e UCs faturadas usam a A5 (`kpis_mensal`). Com filtros regionais ou de classe, usam a A3 (`fato_segmento_mensal`), agregada por mês.

Receita de energia e consumo são somados exclusivamente nos meses selecionados. O preço médio corresponde à soma de `receita_energia` dividida pela soma do consumo, sem média simples dos preços. UCs faturadas usam a última competência, sem somar contagens mensais.

Uma competência ausente invalida os acumulados que dependem dela. Valores nulos permanecem indisponíveis, zeros presentes são preservados e denominador zero não produz uma razão. Sem referência ou sem os valores necessários, a variação fica nula; uma referência zero não produz variação percentual relativa.

A validação de cada indicador depende da disponibilidade e da integridade das tabelas exigidas pelo contrato Gold.

## Cadastro e geração distribuída

`GET /api/dashboard/cadastro-gd` consulta exclusivamente a competência final de cada intervalo na A5, usando `qtd_ucs_cadastradas` e `qtd_ucs_com_gd`.

A consulta não soma meses nem substitui uma competência ausente.

O percentual de geração distribuída é calculado por:

`percentual_gd = qtd_ucs_com_gd / qtd_ucs_cadastradas * 100`

Denominador zero ou valor indisponível resulta em percentual nulo.

`CadastroGdResponse` contém `atual`, `referencia` opcional e `variacao_cadastradas_pct`, comparando as posições finais quando válidas.

Essa rota é global e aceita somente filtros temporais.

## Consumo por classe

`GET /api/dashboard/consumo-classes` soma `consumo_kwh` da A3 por classe e intervalo.

Retorna RESIDENCIAL, COMERCIAL, INDUSTRIAL, PODER PUBLICO e RURAL em ordem decrescente de volume principal, com valores indisponíveis ao final. Não aplica filtros regionais ou de classe.

- Participação: `consumo_classe / consumo_total * 100`.
- Variação: `(consumo_principal - consumo_referencia) / consumo_referencia * 100`.
- A ausência de uma classe em qualquer mês selecionado invalida seu volume consolidado; ela não é interpretada como zero.
- Se algum volume estiver indisponível, o total e as participações também ficam nulos.
- Um zero registrado continua válido; total zero não produz participação.
- Referência zero ou ausente não produz variação percentual.

A resposta inclui os volumes de referência e listas de competências ausentes. Segmentos duplicados e classes desconhecidas são reportados para evitar agregações silenciosamente incorretas.

`ConsumoClassesResponse` fornece uma única série principal para as barras. O volume de referência serve à variação e ao tooltip, sem exigir barras duplas.

## Série mensal do Dashboard

`GET /api/dashboard/serie` utiliza a A5 (`kpis_mensal`) sem filtros e agrega a A3 (`fato_segmento_mensal`) por competência quando há município, bairro ou classe.

Os campos da resposta são `competencia`, `receita`, `energia_kwh` e `tarifa_media`.

Receita corresponde à energia faturada, sem tributos. Os pontos são mensais, sem acumulação progressiva. O preço mensal divide a soma da receita pela soma do consumo, com quatro casas decimais. Receita e consumo têm duas casas na resposta, como os KPIs principais.

Sem parâmetros temporais, retorna o histórico inteiro do catálogo, correspondente a 48 meses na base do case.

Com `atual_*`, `base_*` ou `comparar`, mantém as validações do Dashboard e retorna somente os intervalos selecionados, em ordem cronológica e com as competências reais. A comparação opcional consulta cada intervalo separadamente, sem ler os meses entre eles.

Uma competência ausente mantém seu ponto com valores `null`; não é preenchida com zero nem substituída por outro mês. Nulos de uma métrica preservam as demais quando disponíveis. Zeros presentes são mantidos, e consumo zero torna `tarifa_media` nula.

Uma agregada necessária ausente continua retornando HTTP `501`. A consulta não depende de faturas globais nem da A8.

Os gráficos do frontend consomem essa série pela API. A fonte de dados continua sendo mock ou SQLite, conforme `DATA_SOURCE`.

## Faturamento em aberto no Dashboard

O KPI de inadimplência usa a A3 (`fato_segmento_mensal`), inclusive na visão geral:

`SUM(valor_em_aberto) / SUM(receita_total) * 100`

O denominador inclui tributos.

A consulta preserva as competências selecionadas e a situação conhecida até 30/06/2026. Inclui todas as faturas em aberto, mesmo as ainda não vencidas, sem usar `dias_atraso`.

Esse consolidado é derivado para o intervalo solicitado; não substitui o indicador mensal da A5.

- `valor_atual` e `valor_base`: taxas consolidadas, ou `null` quando indisponíveis.
- `variacao_pp`: principal menos referência, em pontos percentuais.
- `variacao_pct` e `variacao_abs` ficam nulos para inadimplência.
- Sem referência, não há variação.
- `inadimplencia`: taxa da última competência, competências ausentes de cada intervalo e `data_corte`. A taxa final não recebe uma segunda comparação.

Uma competência ausente invalida o consolidado inteiro, preservando a taxa final quando disponível. Valores monetários nulos, não finitos ou negativos invalidam a razão afetada; denominador zero não produz uma taxa. Registros presentes com zero não são lacunas.

Segmentos duplicados são reportados em vez de agregados duas vezes.

Para um único mês, a tela apresenta apenas a taxa mensal. Em vários meses, destaca o consolidado e mostra a última competência como informação secundária.

## Diagnóstico de conta alta

`GET /api/unidades/{uc}/visao-360` aceita `competencia_atual` e `competencia_referencia` em `YYYY-MM`.

O padrão é a última competência disponível da UC e a competência anterior disponível. A referência deve ser anterior ao mês analisado; os seletores mostram somente meses com histórico.

Exemplo:

```text
/api/unidades/UC000001/visao-360?competencia_atual=2026-06&competencia_referencia=2025-06
```

A resposta identifica as competências e separa totais, percentuais e classificações de consumo (kWh) e faturamento (`valor_total`, R$).

Dados ausentes e referência zero possuem mensagens próprias.

Os limites das faixas ficam nas constantes `LIMITE_VARIACAO_PEQUENA_PCT` e `LIMITE_VARIACAO_MODERADA_PCT`, em `app/services/unidades.py`.

O histórico geral não depende desse filtro.

## Outros blocos da Visão 360

- **Faturas:** `faturas` contém a última fatura; a listagem consulta a rota paginada, com 10 registros por página. `resumo_faturas` considera todas as competências da UC, independentemente dos filtros.
- **Trocas de medidor:** `trocas_medidor` preserva as 13 colunas da A6. As médias excluem o mês da troca; gráfico e diagnóstico sinalizam a competência usando a flag da A2, sem inferir causalidade.
- **Interrupções:** `periodo_interrupcoes=6_meses|12_meses|todos` atualiza ocorrências da UC e contexto do alimentador. O padrão é 12 meses. DEC/FEC utilizam os indicadores mensais da A8.
- **Atendimentos:** a API mantém `periodo_atendimentos=6_meses|12_meses|todos`, com padrão de 12 meses. A tela solicita `todos` e aplica situação, contagens e paginação no frontend.

A disponibilidade de cada bloco depende das tabelas e colunas necessárias na fonte selecionada.

## Testes e validação

Os testes automatizados do backend são executados com `pytest`.

Na validação local registrada para a versão atual do ambiente, foram obtidos os seguintes resultados:

| Verificação | Resultado |
|---|---|
| Testes de contrato da Gold | 65 aprovados |
| Suíte completa do backend | 1.632 aprovados e 19 ignorados |
| Testes do frontend | 75 aprovados |
| Build do frontend | Concluído com sucesso |
| Instanciação do repositório SQLite | Validada |
| Execução local da aplicação | Verificada |

Os testes do backend devem ser executados a partir da raiz do repositório, utilizando o ambiente virtual do backend:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest .\backend\tests -q
```

Para executar somente os testes de contrato da Gold:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest .\backend\tests\agent\test_sql_gold_contract.py -v
```

Os testes automatizados não substituem a validação manual dos fluxos da aplicação. Os resultados acima registram uma execução específica e não garantem que futuras versões mantenham os mesmos resultados.

**Observação:** a suíte geral foi executada com a configuração de testes do projeto, que utiliza dados mockados. A validação do contrato Gold e a execução local com SQLite são verificações complementares.

## Premissas e limitações

- **Dados mockados:** o conjunto de referência contém 400 UCs e 48 competências, de julho de 2022 a junho de 2026.
- **Persistência:** as ordens de inspeção ficam no SQLite do portal (`backend/data/portal.db`, criado quando necessário) e sobrevivem a reinícios. Para reiniciar esse estado, pare o servidor e remova o arquivo somente se tiver certeza de que os dados podem ser descartados. O caminho pode ser alterado por `PORTAL_DB_PATH`.
- **Fonte dos dados:** `DATA_SOURCE=mock` seleciona o repositório mockado; `DATA_SOURCE=sqlite` seleciona o repositório SQLite.
- **Gold local:** a Gold é um artefato externo ao Git e deve ser obtida pela equipe conforme o procedimento de DADOS.
- **Limitações de SQLite:** a disponibilidade dos endpoints depende das tabelas e colunas existentes. Algumas consultas, como a consulta global de faturas da análise de receita, permanecem limitadas no modo SQLite.
- **Efeito-preço:** inclui reajuste, bandeira e mix de classes.
- **Continuidade:** na Visão 360, DEC/FEC descrevem o alimentador; a quantidade e a duração do histórico descrevem a própria UC. A base mensal de UCs e o impacto em UC × horas acompanham os indicadores.
- **Fila de perdas:** uma UC com ordem ativa sai da fila de suspeitas. O score de prioridade corresponde à probabilidade multiplicada pelos kWh/mês recuperáveis.
- **IA:** a rota `/api/ia/perguntar` está identificada como stub; sua existência não significa que todos os fluxos de IA estejam homologados com a Gold SQLite.
- **Homologação:** a execução local com a Gold atualizada foi validada. A reprodução do processo de exportação oficial e a validação integrada devem seguir os procedimentos e critérios da equipe de DADOS.

## Documentação relacionada

- [`docs/contrato-gold.md`](docs/contrato-gold.md): mapeamento das tabelas, campos, consultas e limitações da Gold.
- README principal do repositório: visão geral do produto, arquitetura, módulos e instruções para executar a aplicação completa.
