# Camada 7 — Finalização operacional

## Arquitetura e fluxo

```text
request_id único → C1 → memória/contexto → C2 GET
                                        ├─ HIT: resultado final
                                        └─ MISS: C4.1 → C4.2 → C4.3 → C4.4 → C5 → C6
                    → finalize_request → finalizer
                        ├─ auditoria → portal.db
                        ├─ memória elegível → Redis
                        └─ C2 SET elegível, uma única vez → Redis
                    → entrega
```

Reutiliza `state/service.py`, `records.py`, `finalizer.py` e suas políticas.
`answer_question` cria o ID uma vez na entrada. Toda saída terminal passa por
`finalize_request` e recebe o mesmo ID na resposta interna e no AuditRecord.
Requisições seguintes e HIT têm IDs novos; o payload cacheado não contém IDs.

O SET direto foi removido do pipeline. A C2 continua dona de chave/codec/política;
só o finalizer chama `write_cache`. Recebe a chave original da preparação da
requisição, sem recalculá-la depois da atualização de memória.

Somente `ANSWERED` completo e comprovadamente não truncado é cacheado, após
aprovação e C6. Completude exige síntese ANSWERED e `row_count == len(rows)`.
HIT, NO_DATA, esclarecimentos, bloqueios e erros não fazem SET.

## SQLiteAuditStore e portal.db

O factory existente agora fornece `SQLiteAuditStore(settings.portal_db_path)`.
Construção/import não abre conexão nem cria diretório/tabela. O primeiro save
cria `agent_audit` de forma idempotente, com exatamente os campos de AuditRecord.

- `request_id` é chave primária única; repetir o mesmo ID não duplica nem
  sobrescreve o registro original.
- Timestamp convertido para UTC em ISO 8601; outcome/provider_error textuais.
- Booleanos como INTEGER 0/1; `truncated` desconhecido permanece NULL.
- INSERT parametrizado; SQL pode constar somente nesta auditoria interna.
- Uma conexão/transação por save, fechada ao fim; não compartilha a conexão
  síncrona das ordens. Segue o padrão existente de diretório/transação do portal.
- I/O em `asyncio.to_thread`, timeout/busy timeout SQLite de 1 segundo.
- Finalizer limita a tentativa de auditoria a 2 segundos e preserva a resposta
  em falha. Cancelar a espera não interrompe à força uma thread SQLite já ativa.

Gold permanece somente leitura. `agent_audit` coexiste com `ordens_inspecao`
em `PORTAL_DB_PATH`; nenhum banco paralelo de auditoria é criado.

## RedisMemoryStore

Memória curta disponível quando `REDIS_URL` está configurada. Chave:

```text
agent:memory:v1:<SHA-256 do session_id>
```

O session_id bruto não aparece na chave. Cada item é JSON revalidado de
`MemoryEntry`: somente pergunta, resposta e outcome do contrato existente.
Credenciais de configuração, SQL, request IDs e metadados de providers não são
inseridos na memória. Entradas/payloads incompatíveis causam UNAVAILABLE;
não são interpretados como sessão vazia.

RPUSH + LTRIM + EXPIRE são executados em transação Redis. Preserva as últimas
20 interações, renova TTL em todo append e lê no máximo essas 20. O helper de
contexto existente usa no máximo as últimas 5 e 4000 caracteres, priorizando
entradas recentes sem cortar/reparar textos.

Somente ANSWERED, NO_DATA e NEEDS_CLARIFICATION, com sessão e resposta útil,
geram append. Bloqueios e erros não entram na memória. HIT pode gerar append,
mas nunca SET de cache nem reexecução das etapas caras.

Como o HTTP usa `asyncio.run` por pergunta, cada operação abre/fecha cliente e
pool no seu próprio event loop, usando o factory Redis compartilhado com C2.
Nenhum singleton async ou conexão antecipada foi introduzido.

## Outcomes e falhas secundárias

Todos os enums existentes foram integrados, sem criar novos status:

- ANSWERED e NO_DATA conforme a síntese aprovada.
- NEEDS_CLARIFICATION, OUT_OF_SCOPE, INSUFFICIENT_CONTEXT e REQUEST_REJECTED
  conforme o status existente da geração.
- INPUT_BLOCKED, SQL_BLOCKED e OUTPUT_BLOCKED para rejeições dos guardrails.
- PROVIDER_ERROR e EXECUTION_ERROR para suas falhas tipadas.
- INTERNAL_ERROR para falhas internas dos guardrails, C6 sem resultado ou
  exceção inesperada do pipeline, sempre com mensagem segura.

Auditoria, memória e cache têm tentativas independentes. Falhar um não impede
os demais nem altera a resposta. Logs incluem apenas tipos de exceção, sem
payload/URL/SQL. Cancelamento da requisição continua sendo propagado.

Leitura de memória tem deadline no adapter e na preparação do estado. Falha ou
timeout mantém `MemoryContextStatus.UNAVAILABLE`, sem GET nem SET de cache;
o pipeline segue sem cache. EMPTY permanece uma leitura bem-sucedida vazia.

## Configuração e Docker

Reutiliza `PORTAL_DB_PATH`, `REDIS_URL` e as configurações da C2, inclusive
`GOLD_DATA_VERSION` explícita quando cache habilitado. Adições no Settings,
`.env.example` e Compose:

| Variável | Padrão | Validação |
|---|---|---|
| MEMORY_TTL_SECONDS | 86400 | Inteiro positivo. Renovado no append. |
| MEMORY_TIMEOUT_SECONDS | 1 | Positivo e finito, por leitura/escrita. |

Não há segundo Redis. Redis continua sem porta publicada, sem volume persistente
e sem dependência crítica do backend. Sua memória é efêmera na recriação; o TTL
não implica persistência. Auditoria permanece no volume `portal_data` RW; Gold RO.

## Validação

**335 testes locais passaram** na rodada final de C2/C7, pipeline e API.
Cobrem adapter SQLite (campos, UTC, ID único, concorrência,
coexistência com ordens e timeout de lock), Redis simulado (JSON, política,
limite, TTL e falhas), contexto 5/4000, todos os outcomes terminais, ID único,
HIT auditado/lembrado, SET único, truncamento e falhas independentes dos stores.

Ensaio real reproduzível, a partir da raiz:

```powershell
$env:GOLD_DATA_VERSION = 'validacao-c7-local-v1' # Só para o ensaio local.
docker compose up --detach --build --wait
Get-Content -Raw backend/tests/manual/validate_c7.py |
    docker compose exec -T backend python - healthy
docker compose stop redis
try {
    Get-Content -Raw backend/tests/manual/validate_c7.py |
        docker compose exec -T backend python - offline
} finally {
    docker compose up --detach --wait redis
}
```

Resultados reais: backend/Redis saudáveis; MISS com um SET, HIT auditado sem SET
e com novo ID; append elegível e bloqueio sem append; memória limitada a 20,
contexto às últimas 5 e TTL renovado. Falha de auditoria por caminho inválido
preservou resposta aprovada. Com Redis parado, health continuou `ok`, a resposta
foi entregue, auditoria persistiu e cache foi bypassado por UNAVAILABLE.
Redis foi religado. Mounts Gold RO/portal RW e ausência de porta Redis publicados
foram conferidos.

O ensaio usa providers determinísticos, mas SQL/guardrails/C6 e stores são reais.
Para verificar HIT com o MESMO contexto, restaura ao estado inicial somente a
memória de sua sessão temporária: append normalmente muda o contexto e a chave,
gerando MISS. Não otimiza compartilhamento nem ignora memória na key.
Chaves próprias de teste são removidas; registros de auditoria de validação
permanecem no portal com perguntas identificadas como validação C7.
Não comprova chamadas a providers autenticados via HTTP.

Após religar Redis, o ensaio C7 saudável foi repetido com sucesso. O ensaio
isolado da C2 também confirmou GET=2, SET=1 e somente uma execução de cada etapa
cara, incluindo SQL Guardrail, executor, Output Guardrail e C6.

## Arquivos desta entrega

- `backend/app/agent/pipeline.py`: ID de entrada, outcomes e ponte única C7.
- `backend/app/agent/state/finalizer.py`: side effects independentes e limitados.
- `backend/app/agent/state/service.py`: parâmetros da ponte de finalização.
- `backend/app/agent/state/dependencies.py`: factory operacional dos três stores.
- `backend/app/agent/state/request_state.py`: timeout e UNAVAILABLE da memória.
- `backend/app/agent/state/memory.py`: defaults de TTL e timeout.
- `backend/app/agent/state/redis_memory.py`: novo adapter de memória curta.
- `backend/app/agent/state/sqlite_audit.py`: novo adapter de auditoria.
- `backend/app/agent/state/redis_client.py`: factory Redis por operação.
- `backend/app/agent/state/redis_cache.py`: reutilização desse factory sem mudar política.
- `backend/app/core/config.py`, `backend/.env.example`, `compose.yaml`: configuração de memória.
- `backend/tests/agent/test_pipeline.py`: terminais, IDs e falhas de finalização.
- `backend/tests/agent/test_cache_config.py`: configuração operacional C2/C7.
- `backend/tests/agent/test_redis_memory.py`: contrato e falhas do adapter Redis.
- `backend/tests/agent/test_sqlite_audit.py`: persistência e comportamento SQLite.
- `backend/tests/manual/validate_c7.py`: ensaio Docker C7 reproduzível.
- `backend/tests/manual/validate_redis_cache.py`: isolamento do ensaio C2.
- `backend/app/agent/docs/C2-cache.md`, `backend/app/agent/docs/C7-finalizacao.md`,
  `docs/dockerizacao.md`: documentação sincronizada.

`state/records.py`, os Protocols e o helper `memory_context.py` foram reutilizados.
O arquivo não rastreado `c7-atual.txt` não foi alterado por esta tarefa.

## Pendências fora desta entrega

- Logfire não implementado.
- E2E com providers autenticados e versão oficial do snapshot por ambiente.
- Retenção/consulta administrativa da auditoria e memória durável não fazem
  parte dos contratos implementados nesta tarefa.
