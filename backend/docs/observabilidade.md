# Observabilidade com Logfire

Estado revisado em **03/11/2026**. O diagnóstico de latência, a lacuna de metadados
da C5 e o contrato atual de resultados escalares estão em
[Diagnóstico de latência e apresentação do Assistente IA](diagnostico-latencia-assistente.md).

## Integração com o pipeline atual

A rota síncrona `POST /api/ia/perguntar` chama `services.ia.perguntar`, que executa
`pipeline.answer_question` via `asyncio.run`. O contexto OpenTelemetry atravessa
o threadpool do FastAPI e esse loop, conforme o teste de correlação.

O pipeline ativo usa C1, C2 GET, os orquestradores de SQL e síntese, C6 e C7.
A C3 corresponde à cadeia de fallback dos providers.
Os providers criam instâncias de `pydantic_ai.Agent` a cada tentativa.

**A C7 está integrada ao pipeline HTTP.** As saídas terminais passam por `finish()`,
que chama `state.service.finalize_request` e `state.finalizer.finalize` antes da entrega.
As dependências padrão fornecem auditoria SQLite no `portal.db` (`PORTAL_DB_PATH`)
e memória curta no Redis quando `REDIS_URL` está configurada. O Cache SET elegível
está centralizado na finalização, sem escrita direta no pipeline.
Falhas de auditoria, memória ou cache têm tratamento independente e não derrubam
uma resposta válida, conforme o [contrato da C7](../app/agent/docs/C7-finalizacao.md).
Se a construção das dependências falhar, o pipeline retorna a mensagem segura sem
chamar a finalização com stores inválidos.

## Configuração

Instalar `pip install -r requirements.txt` e configurar no ambiente ou `.env` local:

```dotenv
LOGFIRE_ENABLED=true
LOGFIRE_TOKEN=<write-token-do-projeto>
LOGFIRE_SERVICE_NAME=v-energy-grid-360-backend
# Opcional: override da região/servidor; padrão inferido pelo SDK a partir do token.
LOGFIRE_BASE_URL=
```

Reiniciar o backend após mudar as variáveis. O padrão é desligado. Token ausente,
SDK ausente, integração incompatível ou falha na inicialização mantém a aplicação
operacional. Não há login interativo, criação automática de projeto ou leitura de
credenciais Logfire de arquivo. O `.env` real não foi modificado.

O SDK Logfire é configurado com uma instância local, sem console nem exportação
automática. Um único exportador OTLP em lote envia ao Logfire **após a filtragem**.
`send_to_logfire=False` nessa instância evita um segundo caminho de envio sem filtro;
não significa que a exportação OTLP filtrada esteja desligada.
O timeout de exportação é de 2 segundos, no worker do exportador.

### Execução no Docker

Na raiz do repositório, carregar explicitamente as configurações locais:

```powershell
docker compose --env-file backend/.env up --detach --build --wait
```

O Compose repassa as chaves dos providers e as variáveis `LOGFIRE_*` listadas em
`compose.yaml`. A existência de `backend/.env` no host não configura, sozinha,
o ambiente do container. O arquivo não é copiado para a imagem nem montado no backend.
Verificar somente a presença das credenciais; `docker compose config` sem `--quiet`
pode exibir seus valores. HTTP 200 em `/api/health` não comprova acesso aos providers.

Somente `/api/ia/perguntar` usa `proxy_read_timeout 300s`; as demais rotas conservam
o padrão Nginx de 60 s. O limite do proxy mede espera entre leituras do upstream.
O backend não tem deadline global: os 20 s configurados são por chamada ao modelo.
Fallbacks e regenerações acumulam duração. Um 504 do proxy pode anteceder a conclusão
do pipeline/C7 e coexistir com um span HTTP 200 do backend. Ver
[diagnóstico e validação do proxy](../../docs/dockerizacao.md#espera-do-assistente-ia).

As variáveis `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` e `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` não são suportadas em paralelo:
se presentes, a observabilidade desta aplicação é desativada para evitar exportadores
automáticos que contornem o filtro. Use `LOGFIRE_BASE_URL` para alterar o destino.

## Spans e atributos

| Span | Operação / atributos específicos |
| --- | --- |
| HTTP, como `POST /api/ia/perguntar` | método, template da rota, status HTTP, `request_id`; duração nativa |
| `agent.pipeline` | resultado final, última etapa, cache, tentativas, providers distintos, regenerações totais, linhas e truncamento quando houve execução |
| `agent.C1` | Input Guardrail: decisão em `outcome` |
| `agent.C2` | cache/memória: `cache_hit` |
| `agent.C4.1` | geração SQL: status/erro categórico, quantidade de tentativas/providers |
| `agent.C4.2` | SQL Guardrail: decisão |
| `agent.C4.3` | execução SQL: status/erro categórico, `row_count`, `truncated` |
| `agent.C4.4` | síntese: status/erro categórico, quantidade de tentativas/providers |
| `agent.C5` | Output Guardrail: decisão |
| `agent.C6` | pós-processamento: `processed` / `not_processed` |
| `agent.C7` | finalização: `request_id`, `outcome`, `cache_hit`, `row_count`, `truncated` e `regenerations` do registro de auditoria, quando disponíveis |
| `agent.provider` | tentativa de Gemini/OpenRouter: provider, modelo, índice da tentativa e sucesso/erro categórico |
| `agent.sql_flow`, `agent.synthesis_flow` | orçamento efetivamente consumido de regenerações em cada orquestrador |
| `pydantic_ai.operation` | spans nativos: operação, provider/modelo e contadores de tokens permitidos quando disponibilizados pelo SDK |

Spans próprios recebem `request_id`, `stage` e `duration_ms`. HTTP, pipeline,
`PipelineResult` e auditoria C7 usam o mesmo ID interno por requisição. Chamadas diretas
ou com observabilidade desligada geram um UUID novo. Requisições seguintes, inclusive
cache HIT, recebem IDs novos. Headers ou campos externos não fornecem esse ID,
e nenhum header novo foi acrescentado às respostas.

Atributos próprios permitidos: `request_id`, `stage`, `outcome`, `cache_hit`,
`row_count`, `truncated`, `regenerations`, `provider_attempts`, `provider_count`,
`provider_attempt`, `provider`, `model`, `duration_ms`.
Providers distintos são contados pelo nome do provider, não pelo número de modelos.
Tentativas incluem as tentativas reportadas pelo fluxo, inclusive falhas de configuração.
Retentativas internas disponibilizadas pelo SDK aparecem nos spans nativos.

### Limite atual do diagnóstico da C5

`agent.C5` exporta a decisão em `outcome`, mas não exporta `reason` ou `retryable`.
A auditoria C7 guarda a contagem total de regenerações; não guarda a resposta
intermediária rejeitada nem a regra responsável pelo bloqueio.

Uma sequência C4.4 → C5 → C4.4 indica a regeneração de síntese após um bloqueio
recuperável, conforme o fluxo atual. Para localizar a etapa que regenerou, consultar
também `agent.sql_flow` e `agent.synthesis_flow`, pois o total no pipeline soma ambas.
O motivo exato de uma rejeição histórica não pode ser inferido apenas pela duração
ou por `outcome=block`.

É recomendada uma extensão futura com motivo categórico validado, `retryable` e
índice da validação, acompanhada de atualização explícita da whitelist e testes
de privacidade. **Essa extensão ainda não foi implementada.** Não exportar
`original_answer`, `unsupported_values`, feedback, pergunta, SQL ou conteúdo de erros.

`agent.C7` aparece no trace quando a finalização é executada, inclusive em cache HIT
e saídas antecipadas que chegam ao finalizador. Sua presença indica execução da etapa;
não há booleano de conexão/persistência nem garantia de sucesso de cada store no span.

As etapas C4.1/C4.2/C4.3 e C4.4/C5 se repetem quando há regeneração, sem alterar os
orçamentos existentes. Saídas antecipadas mostram somente as etapas executadas.
Cache HIT não produz spans de geração/execução/síntese. `cache_hit=false` também
ocorre quando o cache está desabilitado; não é um indicador de disponibilidade Redis.
Linhas/truncamento ficam ausentes se não houve execução, inclusive em cache HIT.

Tokens preservados: entrada, saída, leitura e criação de cache, nos namespaces
`gen_ai.usage.*` e `gen_ai.aggregated_usage.*` explicitamente permitidos. Não somar os
contadores agregados do agente com os contadores por requisição, para evitar duplicação.

## Privacidade e isolamento de falhas

- FastAPI: sem headers, body, argumentos validados ou erros de validação exportados.
- PydanticAI: `include_content=False`, `include_binary_content=False` e
  `include_model_request_parameters=False`, seguindo a
  [documentação oficial](https://pydantic.dev/docs/ai/integrations/logfire/).
- Nenhum argumento das funções é inspecionado pelos decorators; apenas projeções
  explícitas dos resultados fornecem os metadados.
- A lista de atributos permitidos também é aplicada no exportador. URLs completas,
  caminhos com parâmetros resolvidos, query strings, conteúdo de mensagens, SQL,
  resultados da Gold, memória, sessão, payloads e API keys são descartados.
- Nomes de spans automáticos são reconstruídos; rotas usam somente seu template.
  Eventos, links, descrição do status, atributos do escopo de instrumentação e recursos
  de processo são removidos, inclusive mensagens e stacks de exceção.
- O exportador preserva IDs, parentesco, tempos, status e metadados permitidos.
  Falhas de sanitização descartam o lote; nunca enviam o original.
- Inicialização, criação/entrada/atributos/saída de spans e exportação têm isolamento
  de falhas. Exceções de negócio continuam se propagando normalmente.
- Logging Python existente não é integrado ao Logfire. `services.ia` registra apenas
  o `request_id` interno ao concluir uma resposta, sem SQL ou conteúdo. Não adicionar
  um logging handler externo sem revisar essa política.

## Validação

`tests/agent/test_observability.py` usa FastAPI e instrumentação PydanticAI reais,
um modelo sintético PydanticAI, SQLite sintético e exportação em memória. Não envia
telemetria nem solicitações de LLM a serviços externos.
Uma fixture também bloqueia explicitamente requisições a modelos reais nesses testes.

Os testes cobrem inicialização sem opt-in/token/SDK, falhas de configuração e exportação,
falhas no ciclo dos spans, preservação de exceções da aplicação, respostas idênticas
com/sem telemetria, correlação HTTP/pipeline/C7/auditoria, atributos antes e depois do
filtro, tokens, cache HIT, saídas antecipadas, regeneração, truncamento, validação HTTP,
sessão em URL e exceções. Também verificam que falhas de persistência C7 preservam
a resposta aprovada e não exportam o conteúdo das exceções.
Também há proteção contra um exportador OTLP paralelo que contorne a filtragem.

A suíte completa deve ser executada com `python -m pytest tests -q` em `backend`.
No Windows deste ambiente, o sandbox bloqueia o socketpair usado por asyncio/TestClient;
os testes precisam rodar fora desse sandbox. Os testes de integração de providers
dependem de `RUN_LLM_INTEGRATION=1` e ficam desabilitados na suíte de regressão padrão.

Na revisão de configuração Docker: **221 regressões selecionadas aprovadas** (Compose,
providers, observabilidade e C7/pipeline), incluindo os **24 testes de observabilidade**,
e **1.724 aprovados, 19 ignorados na suíte completa**.
`git diff --check` também passou. A validação usou o `.venv` local e exportação em memória.

Na investigação posterior de latência/resultados escalares, **187 testes existentes**
de síntese, C5, C6, contrato de visualização e observabilidade passaram. Houve também
uma execução diagnóstica com providers e Gold reais, usando somente metadados seguros;
seus tempos e tokens estão no [relatório específico](diagnostico-latencia-assistente.md).
Ela é uma nova execução do pipeline, não um replay do trace histórico ou uma medição HTTP.

## Limitações e dívidas

- Redis e SQLite não receberam instrumentação profunda. O tempo agregado de C2/C7
  cobre o trabalho existente; não há spans por comando/query de infraestrutura.
- Não foram adicionados spans de HTTPX, SDKs Gemini/OpenRouter ou logging Python:
  PydanticAI já fornece o nível de chamada ao modelo necessário para esta versão,
  sem abrir caminhos extras de captura de conteúdo.
- Não há métricas exportadas, dashboards, alertas ou sampling configurado nesta versão;
  durações e contadores estão nos spans. A lista explícita de atributos pode precisar
  de atualização ao evoluir Logfire/PydanticAI.
- Exportação é best effort em lote: indisponibilidade do serviço ou término abrupto
  pode perder telemetria. Não há confirmação de entrega nem armazenamento durável local.
- Uma validação adicional da rota FastAPI via TestClient usou o exportador OTLP real:
  lotes de bloqueio C1/C7 e HTTP 422 retornaram `SUCCESS` no envio, e `/v1/info` reconheceu
  o projeto. Posteriormente, o usuário confirmou no Logfire traces reais de 43,1 s
  e 62,1 s. Essa confirmação no produto é distinta da aceitação OTLP e dos testes
  com exportador em memória. A consulta `/v2/query` pelo agente, com o token disponível,
  retornou HTTP 401; o agente não tem acesso de leitura para consultar esses traces.
  O trace específico do 504 continua sem confirmação, conforme a limitação aceita.
- A instrumentação PydanticAI é global ao processo; novas instâncias de Agent também
  usarão esta política sem conteúdo. A instância Logfire fica local à configuração.

## Arquivos desta implementação

Novos: `app/core/observability.py`, `app/core/telemetry_export.py`,
`tests/agent/test_observability.py` e `docs/observabilidade.md`.

Modificados: `.env.example`, `requirements.txt`, `README.md`, `app/main.py`,
`app/core/config.py`, `app/agent/pipeline.py`, `app/agent/sql_generator.py`,
`app/agent/sql_executor.py`, `app/agent/sql_execution_orchestrator.py`,
`app/agent/answer_synthesizer.py`, `app/agent/synthesis_orchestrator.py`,
`app/agent/post_processing_orchestrator.py`, `app/agent/guardrails/input_guardrail.py`,
`app/agent/guardrails/sql_guardrail.py`, `app/agent/guardrails/output_guardrail.py`,
`app/agent/providers/gemini.py`, `app/agent/providers/openrouter.py`,
`app/agent/state/request_state.py` e `app/agent/state/finalizer.py`.

Todos os caminhos acima são relativos a `backend/`. Nenhum commit foi criado.
