# Observabilidade inicial com Logfire

## Análise antes da implementação

A rota síncrona `POST /api/ia/perguntar` chama `services.ia.perguntar`, que executa
`pipeline.answer_question` via `asyncio.run`. O contexto OpenTelemetry atravessa
o threadpool do FastAPI e esse loop, conforme o teste de correlação.

O pipeline ativo usa C1, C2, os orquestradores de SQL e síntese, C6 e a escrita
elegível do cache. A C3 corresponde à cadeia de fallback dos providers.
Os providers criam instâncias de `pydantic_ai.Agent` a cada tentativa.

**A persistência C7 ainda não está conectada ao pipeline HTTP.**
`state.service.finalize_request` e `state.finalizer.finalize` existem e têm testes,
mas não há chamada a eles no pipeline ativo. As dependências padrão de estado
também não instanciam auditoria ou memória. O banco `portal.db` e seus contratos
foram preservados. Ligar essa persistência seria uma mudança funcional.

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
| `agent.C7` | finalizador existente, quando chamado: outcome, cache, linhas, truncamento e regenerações do registro de auditoria |
| `agent.provider` | tentativa de Gemini/OpenRouter: provider, modelo, índice da tentativa e sucesso/erro categórico |
| `agent.sql_flow`, `agent.synthesis_flow` | orçamento efetivamente consumido de regenerações em cada orquestrador |
| `pydantic_ai.operation` | spans nativos: operação, provider/modelo e contadores de tokens permitidos quando disponibilizados pelo SDK |

Spans próprios recebem `request_id`, `stage` e `duration_ms`. O pipeline usa o mesmo
ID do span HTTP; chamadas diretas geram seu próprio ID. Headers externos não fornecem
esse ID, e nenhum header novo foi acrescentado às respostas.

Atributos próprios permitidos: `request_id`, `stage`, `outcome`, `cache_hit`,
`row_count`, `truncated`, `regenerations`, `provider_attempts`, `provider_count`,
`provider_attempt`, `provider`, `model`, `duration_ms`, `c7_persistence_connected`.
Providers distintos são contados pelo nome do provider, não pelo número de modelos.
Tentativas incluem as tentativas reportadas pelo fluxo, inclusive falhas de configuração.
Retentativas internas disponibilizadas pelo SDK aparecem nos spans nativos.

`agent.pipeline` informa `c7_persistence_connected=false`: não simula uma C7 executada.
Não há span C7 no trace HTTP atual. O finalizador está pronto para produzir esse span
quando uma tarefa futura conectar a persistência ao pipeline.

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
- Logging Python existente não é integrado ao Logfire. Por exemplo, o log local de SQL
  em `services.ia` não foi alterado nem encaminhado. Não adicionar um logging handler
  externo sem revisar essa política.

## Validação

`tests/agent/test_observability.py` usa FastAPI e instrumentação PydanticAI reais,
um modelo sintético PydanticAI, SQLite sintético e exportação em memória. Não envia
telemetria nem solicitações de LLM a serviços externos.
Uma fixture também bloqueia explicitamente requisições a modelos reais nesses testes.

Os testes cobrem inicialização sem opt-in/token/SDK, falhas de configuração e exportação,
falhas no ciclo dos spans, preservação de exceções da aplicação, respostas idênticas
com/sem telemetria, ligação HTTP/pipeline, atributos antes e depois do filtro, tokens,
cache HIT, regeneração, truncamento, validação HTTP, sessão em URL e exceções.
Também há proteção contra um exportador OTLP paralelo que contorne a filtragem.

A suíte completa deve ser executada com `python -m pytest tests -q` em `backend`.
No Windows deste ambiente, o sandbox bloqueia o socketpair usado por asyncio/TestClient;
os testes precisam rodar fora desse sandbox. Integrações reais dependem de
`RUN_LLM_INTEGRATION=1` e não fazem parte desta validação.

Resultado da validação nesta implementação: **1.323 testes aprovados, 19 ignorados**
na suíte completa. Desses, **21 casos** pertencem ao novo arquivo de observabilidade.
`git diff --check` também passou. A dependência `logfire[fastapi]` foi instalada no
`.venv` local para validar a integração real com o framework.

## Limitações e dívidas

- C7 de persistência ainda precisa de integração funcional separada.
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
- Não foi validada ingestão no projeto Logfire real: exige token/projeto de destino.
  O formato e a instrumentação foram validados com exportação em memória.
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
