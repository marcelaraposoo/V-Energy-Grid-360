# V-Energy Grid 360

Plataforma que integra unidades consumidoras, medição, faturamento, rede e atendimento da V-Energy numa única
fonte de dados, com portal web e um agente de IA que responde perguntas de negócio em português.

Projeto do case final do Rocket Lab 2026.2 (Visagio). A plataforma é o meio, mas o que o cliente quer é a resposta à
pergunta da diretoria comercial: **por que a receita subiu só cerca de 8%, se a tarifa subiu 10,5% e o volume
faturado caiu cerca de 4%?** A resposta está no [diagnóstico da receita](docs/diagnostico_receita.md) e é
resumida [abaixo](#diagnóstico-da-receita).

## Sumário

- [Visão geral](#visão-geral)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Como executar](#como-executar)
- [Engenharia de dados](#engenharia-de-dados)
- [Portal web](#portal-web)
- [Inteligência artificial](#inteligência-artificial)
- [Diagnóstico da receita](#diagnóstico-da-receita)
- [Dicionário de dados](#dicionário-de-dados)
- [Testes e CI](#testes-e-ci)
- [Decisões e suposições](#decisões-e-suposições)
- [Fora do escopo desta entrega](#fora-do-escopo-desta-entrega)
- [Como contribuir](#como-contribuir)

## Visão geral

```mermaid
flowchart LR
  A["Arquivos brutos<br/>CSV, JSON e XLSX"] --> B["Databricks<br/>Bronze → Silver → Gold"]
  B -->|"CSV no Volume"| C["carregar_sqlite.py"]
  C --> D[("gold.db<br/>SQLite, somente leitura")]
  D --> E["Backend FastAPI"]
  E --> F["Portal web<br/>React + TypeScript"]
  E --> G["Agente de IA<br/>Text-to-SQL"]
  G -->|"SQL SELECT"| D
  G --> H["Gemini / OpenRouter"]
  E --- I[("portal.db<br/>ordens e auditoria")]
  G -.->|"cache e memória<br/>(opcional)"| J[("Redis")]
```

| Módulo | O que entrega | Pasta |
|---|---|---|
| Engenharia de dados | Pipeline Bronze → Silver → Gold no Databricks, Workflow e exportação para o banco local | `data-engineering/` |
| Portal web | Dashboard, análise de receita, visão 360 da UC, fila e ordens de inspeção, qualidade do serviço (DEC/FEC) | `frontend/` e `backend/` |
| Inteligência artificial | Assistente conversacional (Text-to-SQL) e insights dentro do portal | `backend/app/agent/` |
| Diagnóstico da receita | Explicação da variação de receita, com recomendações | `docs/` |

## Estrutura do repositório

| Pasta ou arquivo | Conteúdo |
|---|---|
| `data-engineering/` | Notebooks Databricks (`00` a `04`), YAML do Workflow, scripts de carga do SQLite e notebooks de exploração |
| `backend/` | API FastAPI do portal, repositórios mock e SQLite, e o agente de IA em `app/agent/` |
| `frontend/` | Portal em React + TypeScript (Vite) |
| `docs/` | Dicionário de dados, log de qualidade, diagnóstico da receita, guia de Docker e imagens |
| `compose.yaml` | Stack completa: backend, frontend (nginx) e Redis |
| `.github/workflows/ci.yml` | CI: guarda de arquivos e segredos, testes do backend, lint e build do frontend |

## Como executar

Há três caminhos. O **caminho 2 (Docker)** sobe tudo com a Gold real e é o recomendado para avaliar o projeto.
Os dados brutos e o `gold.db` **não** estão no repositório (já que são confidenciais da Visagio). O caminho 1 mostra como
gerá-los.

### 1. Gerar a Gold (Databricks)

Pré-requisitos: conta Databricks (o projeto foi executado na Free Edition, serverless), um Git folder apontando
para este repositório e os oito arquivos brutos no Volume `/Volumes/v_energy/bronze/landing/` (os arquivos de
leituras em `landing/leituras/`).

1. Abra e execute `data-engineering/workflow/criar_workflow.ipynb`. Ele cria (ou atualiza) o Job
   `v_energy_pipeline` a partir da mesma definição de [`v_energy_pipeline.yaml`](data-engineering/workflow/v_energy_pipeline.yaml).
2. Execute o Job (**Run now**). A ordem é: ambiente → Bronze → 8 Silvers → 10 Golds → export. Se uma checagem de
   qualidade falhar, o notebook para com erro e as tarefas seguintes (incluindo o export) não rodam.
3. Baixe a pasta do Volume `v_energy.gold.export` (contém `manifesto.json` e `<tabela>/part-*.csv`) para
   `data/gold_csv/` na raiz do repositório. A pasta `data/` é ignorada pelo Git.
4. Gere o banco local e confira:

   ```bash
   python data-engineering/scripts/carregar_sqlite.py --entrada data/gold_csv --saida data/gold/gold.db
   python data-engineering/scripts/conferir_sqlite.py data/gold/gold.db
   ```

   O script cria as tabelas com os tipos do manifesto, confere as contagens e só então troca o banco antigo pelo
   novo: se algo falhar, o banco anterior continua como estava.

### 2. Portal completo com Docker (recomendado)

Pré-requisitos: Docker Desktop (engine Linux) com Compose v2 e a porta 8080 livre. Node e Python não precisam
estar instalados. Detalhes e solução de problemas em [docs/dockerizacao.md](docs/dockerizacao.md).

1. Coloque a Gold em `data/gold/gold.db` (caminho 1, ou o arquivo recebido da frente de Dados).
2. Copie `backend/.env.example` para `backend/.env` e preencha (o Docker lê as configurações desse arquivo; ele
   não é versionado):
   - `GOLD_DATA_VERSION`: identifica o snapshot da Gold (obrigatória, usada pelo cache). Troque o valor sempre
     que carregar um `gold.db` novo.
   - `GEMINI_API_KEY` (e, opcionalmente, `OPENROUTER_API_KEY`): necessárias para o Assistente de IA. Sem chave,
     o portal abre e consulta a Gold normalmente.

   O `backend/.env` é opcional para o portal subir: sem ele, o backend usa os valores padrão do `compose.yaml`
   e o Assistente fica sem provedor de IA. Para usar outro arquivo, defina `BACKEND_ENV_FILE`.
3. Suba a stack, passando o mesmo arquivo para o Compose (assim `GOLD_DATA_VERSION` e os demais valores também
   valem na configuração do `compose.yaml`):

   ```bash
   docker compose --env-file backend/.env up --detach --build --wait
   ```

   Sem o `backend/.env` (portal sem Assistente), use `docker compose up --detach --build --wait`.
4. Abra **http://localhost:8080**. `docker compose ps` deve mostrar `backend` e `redis` como *healthy*.

Para parar: `docker compose down`. As ordens de inspeção e a auditoria do agente ficam no volume `portal_data` e
sobrevivem; `docker compose down -v` apaga esse volume.

### 3. Desenvolvimento local, sem Docker

**Backend** (Python 3.11 ou superior):

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # o padrão usa dados mockados (DATA_SOURCE=mock)
uvicorn app.main:app --reload --port 8000
```

Para usar a Gold real, no `backend/.env` defina `DATA_SOURCE=sqlite` e `SQLITE_PATH=../data/gold/gold.db`
(caminhos relativos partem da pasta `backend/`). A documentação interativa fica em http://localhost:8000/docs.
Mais detalhes no [README do backend](backend/README.md).

**Frontend** (Node.js 24 ou superior):

```bash
cd frontend
npm ci
npm run dev
```

Acesse http://localhost:5173. O Vite encaminha `/api` para `http://127.0.0.1:8000`. Mais comandos no
[README do frontend](frontend/README.md).

## Engenharia de dados

Arquitetura Medalhão em PySpark, no catálogo `v_energy` (`bronze`, `silver` e `gold`). As convenções da equipe
estão em [data-engineering/AGENTS.md](data-engineering/AGENTS.md).

| Camada | O que faz | Decisões principais |
|---|---|---|
| Bronze | Ingere as oito fontes como tabelas Delta, sem transformar o conteúdo | Tudo é lido como texto, sem inferência de tipos, para preservar exatamente o que veio da origem. Colunas de auditoria (`ingestion_timestamp`, `source_file`) e a tabela `bronze.controle_ingestao` |
| Silver | Limpa, padroniza e enriquece, um notebook por tabela | Cada tratamento tem uma célula explicando a decisão. Toda linha descartada tem contagem antes e depois. Checagens de qualidade gravadas em `silver.dq_log`. Integridade referencial: faturas órfãs (UCs inexistentes no cadastro) são removidas |
| Gold | Dez tabelas modeladas a partir das perguntas das lideranças | Dimensões e fatos com grão explícito, mais agregados para o portal (KPIs, receita por segmento, DEC/FEC, fila de inspeção) |
| Export | Gold → CSV no Volume → `gold.db` (SQLite) | O banco só tem a Gold e é recriado a cada carga. O banco do portal é outro arquivo |

**Workflow.** O Job `v_energy_pipeline` encadeia 21 notebooks, com paralelismo onde não há dependência, uma
tentativa extra por tarefa (`max_retries: 1`) e limite de 1 hora por tarefa. Print de uma execução bem-sucedida:

![Execução do Workflow no Databricks](docs/img/workflow_execucao.jpeg)

**Estratégia de agendamento.** O Job está definido para rodar uma vez por mês (dia 3, às 03h, fuso
America/Recife) e está **pausado**. Mensal, porque leituras e faturas fecham por competência e os sistemas de
origem geram dados novos uma vez por mês. O dia 3 dá margem para o fechamento do mês anterior, e a madrugada
evita o horário de uso. Ele está pausado porque o dataset do case é uma extração única: em produção basta
retomar o agendamento. Notificação de falha é configurada no workspace.

**Qualidade e rastreabilidade.** Todas as decisões de limpeza estão no [log de qualidade](docs/data_quality_log.md)
e cada tabela Gold tem seu [dicionário](docs/dicionario_dados/README.md), com as decisões que afetam os números.

## Portal web

Frontend React + TypeScript (Vite) e backend FastAPI. O backend lê a Gold por um repositório SQLite (ou mock, em
desenvolvimento) e guarda as ordens de inspeção em `portal.db`. Cada tela responde a um pedido do PDF do case:

| Tela | Rota | Quem pediu | O que resolve |
|---|---|---|---|
| Dashboard Executivo | `/` | Diretoria | Indicadores principais com comparação entre períodos |
| Análise de Receita | `/receita` | Henrique (Comercial) | Variação de receita separada em efeito-preço e efeito-volume, com drill-down município → bairro → classe |
| Visão 360 da UC | `/uc` | Camila (Atendimento) | Cliente, consumo contra o mesmo mês do ano anterior, faturas, medidor, geração solar, interrupções e chamados, com diagnóstico de conta alta |
| Fila e Ordens de Inspeção | `/inspecoes/ordens` | Rafael (Perdas) | Fila priorizada com motivo e energia a recuperar. Gerar, iniciar, registrar resultado e cancelar ordens. Exportar a fila em CSV e importar a planilha de campo |
| Qualidade do Serviço | `/qualidade` | Beatriz (Operação) | DEC e FEC por alimentador ao longo do tempo, principais causas, locais e horas evitáveis |
| Assistente IA | `/assistente` | Patrícia (Tecnologia) | Perguntas em português sobre os dados |

Decisões de produto e UX estão em [frontend/V-Energy-Grid-360-Ideacao-UX.md](frontend/V-Energy-Grid-360-Ideacao-UX.md).
A arquitetura do backend e o mapeamento Gold → API estão em
[backend/docs/arquitetura-backend.md](backend/docs/arquitetura-backend.md) e
[backend/docs/contrato-gold.md](backend/docs/contrato-gold.md).

## Inteligência artificial

O agente é um módulo Python dentro do backend FastAPI (`backend/app/agent/`). Cada pergunta passa por camadas
independentes, cada uma documentada em `backend/app/agent/docs/`:

| Camada | Função |
|---|---|
| [C1](backend/app/agent/docs/C1-guardrail-entrada.md) | Guardrail de entrada: barra tentativas de alterar as instruções do agente antes de qualquer chamada ao modelo |
| [C2](backend/app/agent/docs/C2-cache.md) | Cache opcional de respostas (Redis) |
| [C3](backend/app/agent/docs/C3-fallback-and-quotas.md) | Providers com fallback e controle de quota |
| [C4.1](backend/app/agent/docs/C4.1-sql-generation.md) | Geração do SQL a partir da pergunta |
| [C4.2](backend/app/agent/docs/C4.2-sql-guardrail.md) | Guardrail de SQL, determinístico: só consulta de leitura em tabelas permitidas |
| [C4.3](backend/app/agent/docs/C4.3-execucao-sql.md) | Execução segura do SQL |
| [C4.4](backend/app/agent/docs/C4.4-sintese.md) | Síntese da resposta em português |
| [C5](backend/app/agent/docs/C5-output-guardrail.md) | Guardrail de saída: confere a resposta antes de exibi-la |
| [C6](backend/app/agent/docs/C6-pos-processamento.md) | Pós-processamento e visualização |
| [C7](backend/app/agent/docs/C7-finalizacao.md) | Memória da conversa, cache e auditoria |

**Honestidade.** Quando não há dado para responder, o agente diz que não sabe em vez de inventar. Perguntas fora
do escopo (por exemplo, esportes) e tentativas de manipulação ("ignore as instruções anteriores…") são recusadas.

**Segurança.** O agente só executa SELECT, a Gold é aberta em modo leitura (no Docker, montada como somente
leitura) e as funcionalidades de IA não alteram dados.

**Modelos e fallback.** Ordem atual: Gemini `gemini-3.5-flash-lite`, depois dois modelos gratuitos do OpenRouter e,
por último, Gemini `gemini-3.1-flash-lite`. `PROVIDER_PAYLOAD_POLICY=confidential` (padrão) bloqueia o modelo
gratuito que pode reter dados. Use `synthetic` somente com dados artificiais.

**Auditoria.** Cada pergunta é gravada na tabela `agent_audit` do `portal.db`, com a pergunta, o desfecho, o SQL
executado e a resposta final. Para consultar no Docker:

```bash
docker compose exec backend python -c "import sqlite3; c=sqlite3.connect('file:/data/portal/portal.db?mode=ro', uri=True); [print(r) for r in c.execute('select timestamp, question, outcome, sql from agent_audit order by timestamp desc limit 5')]"
```

**Insights no portal.** Os números dos insights são calculados em Python a partir da Gold (por isso fiéis aos
dados) e o texto pode ser reescrito pelo modelo, com validação contra os valores originais. Hoje eles aparecem na
Fila de Inspeção.

**Avaliação.** A pasta `backend/benchmarks/` compara os modelos candidatos na geração de SQL, com perguntas de
status esperado e SQL de referência, sobre um banco sintético.

**Testes reais de LLM.** Ficam desligados por padrão (custam cota de API). Para rodá-los, defina
`RUN_LLM_INTEGRATION=1` e as chaves.

## Diagnóstico da receita

Resumo (detalhes, tabelas e hipóteses em [docs/diagnostico_receita.md](docs/diagnostico_receita.md)):

1. Os dados reproduzem os números do diretor: receita de energia **+8,00%** e volume **−3,95%**.
2. A receita subiu porque o preço médio por kWh subiu **12,45%** (tarifa e bandeira tarifária): efeito-preço de
   **+R$ 14,09 mi** contra efeito-volume de **−R$ 4,66 mi**. Sem o aumento do preço, a receita teria caído.
3. A queda de volume vem das unidades com painel solar (geração distribuída): 3.510 UCs (7,8%) consumiram 61%
   menos da rede, enquanto as demais cresceram 1,1%.
4. Fora da GD, cerca de 900 UCs em quatro bairros (Iputinga e Macaxeira, no Recife; Jardim Jordão e Prazeres, em
   Jaboatão) tiveram queda de cerca de 55% no consumo a partir de maio/junho de 2025. As inspeções de campo
   confirmaram irregularidade em 92,5% delas: são perdas não técnicas.

## Dicionário de dados

Um arquivo por tabela da Gold, com definição das colunas, grão, decisões de limpeza que afetam cada métrica e
cuidados de uso: [docs/dicionario_dados/](docs/dicionario_dados/README.md).

## Testes e CI

```bash
# backend (usa dados mockados; os testes de LLM real são pulados sem RUN_LLM_INTEGRATION=1)
cd backend && python -m pytest -q

# frontend
cd frontend && npm run lint && npm test && npm run build
```

O CI (`.github/workflows/ci.yml`) roda a cada pull request e a cada push na `main`:

- **Arquivos e segredos:** bloqueia `.env`, `.venv`, `node_modules`, bancos `.db` e chaves de API no código.
- **Backend:** suíte completa do `pytest`, em Python 3.11.
- **Frontend:** lint (`npm run lint`) e build (`tsc` + `vite build`).

O CI **não** roda `npm test` nem valida o `compose.yaml` ou constrói as imagens Docker. Antes de abrir um pull
request, rode esses passos localmente:

```bash
cd frontend && npm test
docker compose config --quiet
```

## Decisões e suposições

- **Definições.** Primeiro ano = competências `2022-07` a `2023-06` (primeiros 12 meses do histórico); últimos 12 meses = `2025-07` a `2026-06`.
  Receita = `valor_energia` (sem tributos); volume = `consumo_kwh` das leituras.
- **Efeito-preço.** Inclui reajuste, bandeira tarifária e mudança de mix entre classes.
- **Trocas de medidor.** No mês da troca, o consumo é a leitura atual. Sem esse tratamento, a variação de volume
  seria distorcida.
- **Integridade.** 32.285 faturas órfãs (UCs que não existem no cadastro) são removidas na Silver.
- **DEC e FEC.** Cada ocorrência de rede é uma UC interrompida. DEC = horas interrompidas ÷ UCs do alimentador no
  mês; FEC = interrupções ÷ UCs. Para um conjunto de alimentadores, soma-se o numerador e o denominador. Os
  valores são simplificados e servem para comparar alimentadores e períodos, não para comparar com os limites
  regulatórios reais. `OSCILACAO` entra no cálculo.
- **Causa ausente.** Ocorrências sem causa entram no DEC/FEC e contam como não evitáveis, então as horas evitáveis
  são um piso.
- **Evento de julho de 2025.** Pico de ocorrências e chamados, com 97% de causa climática e 72% em três
  alimentadores. Foi mantido como evento real, não como erro.
- **Fila de perdas.** O score de prioridade é a probabilidade de irregularidade multiplicada pelos kWh/mês
  recuperáveis. Uma UC com ordem ativa sai da fila.
- **Persistência.** A Gold é somente leitura. Ordens de inspeção e auditoria do agente ficam em `portal.db`,
  separado, para a recarga da Gold não apagá-las.
- **Redis.** Opcional: faz cache de respostas e guarda a memória da conversa. Sem `REDIS_URL`, o agente funciona
  sem cache.
- **Mock e SQLite.** Compartilham o mesmo contrato de API. O padrão do desenvolvimento local é o mock; o Docker
  usa sempre a Gold real.

## Fora do escopo desta entrega

- Login com perfis de acesso por cargo (diferencial do case)

- Uma branch por tarefa (`dados/...`, `dev/...`, `ia/...`) e PR para `main` com 1 revisão.
- Mensagens de commit no formato `tipo(escopo): descrição` (por exemplo, `feat(backend): ...`).
- Nunca versionar dados brutos, o PDF do case ou credenciais (veja o `.gitignore`).
