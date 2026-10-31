# Camada 2 — Cache de respostas finais

## Objetivo e estado atual

O cache é uma otimização determinística: pode evitar repetir chamadas a modelos,
SQL e síntese, mas sua falha não deve impedir uma resposta do agente.

**A C2 ainda não está operacionalmente integrada.** Existem contratos, helpers e
testes com stores simulados; `answer_question` ainda não conecta GET/HIT/SET.
Não há adapter Redis, cache semântico nem auditoria persistente nesta etapa.

## Posição no pipeline

```text
Pergunta → C1 → pergunta normalizada + contexto efetivo + versão Gold
          → GET
             ├─ HIT válido → entrega + futura finalização, sem novo SET
             └─ MISS/falha → agente/SQL/síntese/guardrails/pós-processamento
                            → SET elegível → entrega
```

Um HIT futuro deve pular providers, SQL, síntese, Output Guardrail e
pós-processamento: o valor já representa uma resposta final aprovada da mesma
versão de comportamento. C1, preparação do contexto, validação do payload e
identificação da requisição continuam necessárias. Valor inválido vira MISS;
a C2 não tenta corrigir respostas antigas.

## Componentes e interfaces

- `state/cache.py`: `CacheStore` (Protocol), política, codec JSON e helpers de
  leitura/escrita com timeout.
- `state/cache_key.py`: chave SHA-256 versionada.
- `state/dependencies.py`: configuração injetada de stores, snapshot, TTL e timeout.
- `state/request_state.py`: contexto de memória, chave e GET, sem executar o agente.
- `state/finalizer.py` e `state/service.py`: somente a fronteira existente de SET;
  não representam integração operacional nem conclusão da Camada 7.

## Cache key e sessão

`build_cache_key` recebe `normalized_question` diretamente da C1, o
`memory_context` efetivamente encaminhado ao agente, `session_id` e `data_version`.
Não normaliza novamente nem aplica `casefold`: literais como `'WEB'` e `'web'`,
assim como diferenças no contexto, permanecem distintos.

Um JSON determinístico desses campos é transformado em SHA-256:

```text
agent:answer:v2:<digest SHA-256>
```

Pergunta, memória e sessão não aparecem em texto puro na chave. O namespace `v2`
invalida chaves da normalização anterior. Mudanças incompatíveis de payload ou
comportamento exigem novo namespace; TTL não resolve incompatibilidade.

`session_id` permanece na chave para priorizar isolamento. Não há compartilhamento
inteligente entre sessões. O digest não autentica a propriedade de uma sessão.

## Memória e contexto efetivo

`prepare_request_state` recebe a pergunta já aprovada/normalizada pela C1 e
constrói o contexto antes da chave. `RequestState.memory_status` distingue:

| Estado | Significado |
|---|---|
| `NOT_REQUESTED` | Não houve carregamento: falta sessão ou store de memória. |
| `EMPTY` | Carregamento bem-sucedido, sem contexto útil selecionado. |
| `LOADED` | Contexto carregado e disponível em `memory_context`. |
| `UNAVAILABLE` | Falha ao carregar/preparar o contexto necessário. |

Em `UNAVAILABLE`, não ocorre GET e `cache_key=None` também impede o SET posterior.
O chamador recebe o estado de falha e pode continuar o fluxo normal sem cache;
não deve reinterpretá-lo como memória comprovadamente vazia. `EMPTY` permite
consulta normal ao cache. O mesmo contexto usado na chave deve chegar ao agente.
A seleção de quando exigir memória pertence à integração, não a uma análise
semântica nova dentro do cache.

## Versão do snapshot Gold

Com `cache_store` configurado, `AgentStateDependencies.data_version` é obrigatória
e não pode ser vazia. Configuração inválida é rejeitada com `ValueError`. Sem
store, a execução sem cache não exige versão. O construtor de chave também a exige.

O código recebe um identificador explícito de snapshot; não descobre a versão
por `mtime`, não calcula hash do `gold.db` por requisição e não inventa a sua
publicação. A origem confiável desse identificador depende do acordo com Dados.
Snapshot e versão precisam permanecer coerentes durante a execução.

O SET recebe a chave original e `cache_data_version` da mesma execução. Sem
versão válida ou sem chave, é ignorado. Não recalcule a chave após atualizar
memória ou trocar a versão dos dados.

## Política de GET e SET

Somente `AgentOutcome.ANSWERED` é elegível. A fronteira de escrita exige também:

- `cache_value` final do tipo `PostProcessingResult`, após aprovação e C6;
- `cache_response_complete=True`, explicitamente informado pelo chamador;
- execução comprovadamente não truncada (`audit_record.truncated is False`);
- chave e versão válidas e ausência de HIT.

Resposta parcial, truncamento desconhecido, `NO_DATA`, `NEEDS_CLARIFICATION`,
erros e bloqueios não recebem SET. O default de completude é falso. Em HIT,
a futura integração deve preservar `cache_hit=True` na finalização para evitar
reescrita e permitir o registro da entrega com os IDs da requisição atual.

## Payload e adapter futuro

O valor permanece `PostProcessingResult`: `answer`, `assumptions` e
`visualization`. Não contém IDs de uma requisição anterior.

O adapter deverá usar JSON: `serialize_cache_value` valida antes de serializar,
e `deserialize_cache_value` revalida com Pydantic em modo estrito. JSON inválido
ou incompatível retorna `None` (MISS), sem migração ou reparo. `read_cache` também
rejeita retornos incompatíveis de stores e revalida modelos recebidos.

O adapter Redis ainda terá de implementar persistência, expiração e operações
assíncronas que respeitem cancelamento e timeouts de conexão/operação. Não deve
bloquear o event loop com I/O síncrono.

## TTL, timeout e falhas

- TTL inicial único: **300 segundos**, configurável em `cache_ttl_seconds`.
- TTL deve ser um inteiro positivo; não substitui `data_version`.
- Timeout inicial por GET/SET: **1 segundo**, configurável em
  `cache_timeout_seconds`, sempre positivo e finito.
- `read_cache` e `write_cache` limitam a espera com `asyncio.timeout`, além dos
  limites que o futuro adapter deve aplicar ao transporte.
- Falha/timeout de GET → MISS; falha/timeout de SET → retorno normal ao chamador.
- Payload inválido → MISS ou escrita ignorada; nenhum dado é reparado.

Os helpers registram apenas o tipo de exceção em log, sem pergunta ou payload.
Não há persistência de auditoria. Os timeouts aqui delimitam operações de cache,
não implementam limites para memória/auditoria de outras camadas.

## Testes e pendências

Os testes cobrem chave literal e contexto exato, sessão/versão, versão ausente,
memória vazia/indisponível, JSON incompatível, GET/SET com falha e timeout,
TTL, completude/truncamento, outcomes e ausência de rewrite em HIT.

Permanecem pendentes: adapter Redis e expiração real, publicação do identificador
Gold e integração GET/HIT/SET no pipeline. Os testes usam stores/providers
simulados e não comprovam cache operacional no endpoint.
