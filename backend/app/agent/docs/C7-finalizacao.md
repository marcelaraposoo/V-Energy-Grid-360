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
Se o factory de dependências falhar durante a requisição, a resposta recebe
`INTERNAL_ERROR`, mensagem segura e request_id, sem tentar finalizar com stores
que não foram construídos. A validação de `Settings` no import de `app.main`
continua fail-fast: configuração inválida impede o startup do backend.

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
inseridos na memória. JSON inválido, schema incompatível ou outcome inelegível
geram `CorruptedMemoryError`, distinguindo corrupção de conexão/timeout.
O adapter tenta remover somente a chave de memória da sessão corrompida. Mesmo
quando o DELETE funciona, a requisição que detectou o problema fica UNAVAILABLE,
sem contexto, GET/SET de cache, append ou renovação de TTL. Na próxima requisição,
a leitura vazia permite retomar normalmente o cache e a gravação de memória.
Falha na limpeza mantém a degradação segura; a próxima leitura pode tentar de novo.
Falhas de conexão/timeout na leitura propagam sem DELETE: indisponibilidade não
é evidência de corrupção e não autoriza apagar a sessão.

RPUSH + LTRIM + EXPIRE são executados em transação Redis. Preserva as últimas
20 interações, renova TTL em todo append e lê no máximo essas 20. O helper de
contexto existente usa no máximo as últimas 5 e 4000 caracteres, priorizando
entradas recentes sem cortar/reparar textos.

Somente ANSWERED, NO_DATA e NEEDS_CLARIFICATION, com sessão, memória disponível
na preparação e resposta útil,
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
o pipeline segue sem contexto e sem cache. A finalização não recebe o store de
memória nesse caso: não há append nem renovação de TTL, ainda que o Redis volte
antes da entrega. Auditoria continua sendo tentada. EMPTY permanece uma leitura
bem-sucedida vazia e permite append/cache normalmente.

## Isolamento de sessão — pendência com DEV

O fluxo atual foi verificado no código:

1. `frontend/src/features/assistente/AssistentePage.tsx` gera o identificador no
   navegador com `crypto.randomUUID()` (fallback com timestamp/Math.random),
   mantém em `useRef` e envia `sessao_id` no JSON de cada pergunta. Nova conversa
   troca o ID e chama o endpoint de limpeza para o anterior.
2. `frontend/src/api/endpoints.ts` e `http.ts` enviam esse JSON para
   `POST /api/ia/perguntar`. A camada HTTP não acrescenta identidade autenticada.
3. `backend/app/schemas.py::PerguntaIn` aceita `sessao_id` opcional fornecido pelo
   cliente. `routers/ia.py::perguntar` o repassa a `services/ia.py::perguntar`, que
   chama `answer_question(..., session_id=sessao_id)` sem verificação de propriedade.
4. O pipeline usa esse ID para memória, chave de cache e auditoria. Não recebe
   usuário/tenant autenticado. O backend em `app/main.py` e a rota não configuram
   autenticação nem autorização por proprietário. CORS não cumpre essa função.

**Risco aberto antes de ambiente multiusuário:** quem fornecer o mesmo ID pode
reutilizar/alterar o contexto daquela sessão. A separação por chave impede mistura
acidental entre IDs distintos, mas não verifica se o solicitante é dono da sessão.
SHA-256 apenas evita o identificador bruto na chave Redis; não é autenticação,
autorização ou controle de propriedade. UUID no cliente também não substitui isso.

DEV precisa definir a identidade autenticada, vincular a sessão ao proprietário
(e tenant, se aplicável) e autorizar leitura, escrita e limpeza antes de chamar a
IA. O endpoint `DELETE /api/ia/sessoes/{sessao_id}` atualmente chama um stub sem
efeito; sua implementação também deverá aplicar essa autorização. Nenhum mecanismo
de autenticação foi criado dentro da camada de IA nesta revisão.

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

Regressões do review C7 cobrem falha do factory com resposta segura, dependências
injetadas, startup inválido em processo isolado, leitura indisponível/timeout sem
append, timeout de append após leitura válida, corrupção JSON/schema/outcome,
DELETE restrito à sessão e recuperação na requisição seguinte. A recuperação usa
o adapter Redis com cliente simulado e verifica ausência de EXPIRE/GET/SET na
requisição degradada, auditoria preservada e retomada de append/cache depois.
Também verificam ausência de DELETE em indisponibilidade/timeout e retentativa
quando a limpeza da corrupção falha.

Nesta revisão, a suíte relevante executada a partir de `backend/` passou:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agent tests/test_api.py --ignore=tests/agent/integration -q
# 1163 passed
```

O recorte inicial de pipeline, RedisMemoryStore, configuração e preparação de
estado passou com 144 testes. Providers externos e Redis real não foram usados
nesta revisão; os ensaios Docker descritos abaixo pertencem à validação original.

Na validação original da entrega, **335 testes locais passaram** na rodada final
de C2/C7, pipeline e API.
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

- Propriedade/autorização de sessão depende de DEV e bloqueia uso multiusuário
  seguro, conforme análise acima.
- Logfire não implementado.
- E2E com providers autenticados e versão oficial do snapshot por ambiente.
- Retenção/consulta administrativa da auditoria e memória durável não fazem
  parte dos contratos implementados nesta tarefa.


## Cache automático e inatividade

HIT continua auditado sem novo SET. O turno da entrega é lembrado quando muda
o referente; duplicatas consecutivas iguais são evitadas atomicamente no Redis.
Leituras válidas também renovam a expiração por inatividade, sem append. Ver
[C2-cache.md](C2-cache.md) para TTLs, limites e a proposta de intenção resolvida.
