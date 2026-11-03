# Camada 2 — Cache de respostas finais

## Implementado

Cache Redis opcional integrado a `answer_question`, reutilizando `CacheStore`,
codec JSON/Pydantic, `prepare_request_state`, chave e política já revisados.

- Adapter assíncrono `state/redis_cache.py`: GET e SET com expiração.
- GET/HIT/SET no pipeline real; a rota HTTP repassa `sessao_id`.
- TTL padrão de **300 segundos**; timeout de **1 segundo por operação**.
- `GOLD_DATA_VERSION` explícita e obrigatória quando cache habilitado.
- Falha/timeout de GET vira MISS; falha/timeout de SET preserva a resposta.
- Redis no Compose, sem porta publicada, persistência ou dependência de startup.

## Fluxo GET/HIT/SET

```text
Pergunta → C1 → pergunta normalizada
               → prepare_request_state (contexto + chave original + GET)
                  ├─ HIT → entrega PostProcessingResult, sem novo SET
                  └─ MISS/falha → C4.1 → C4.2 → C4.3 → C4.4 → C5 → C6
                                  → C7: auditoria + memória + SET elegível → entrega
```

HIT pula providers, geração/validação/execução SQL, síntese, Output Guardrail e
pós-processamento. C1 e revalidação Pydantic do payload continuam necessárias.
O resultado interno mantém `outcome=ANSWERED`, `cache_hit=True` e um `request_id`
novo. SQL e tentativas dos providers não são recuperados. Toda entrega passa
pela [C7](C7-finalizacao.md), inclusive HIT, com auditoria e memória elegível.

SET ocorre uma única vez, no finalizer C7, usando a chave calculada no início.
O pipeline não chama `write_cache` diretamente. Exige resposta aprovada e
pós-processada, outcome e síntese `ANSWERED`, resultado não truncado e
`row_count == len(rows)`. `NO_DATA`, esclarecimentos, bloqueios, erros,
incompletude e HIT não geram SET. O status de entrega existente do pipeline
não substitui o outcome na decisão de cache.

## Configuração operacional

Configuração no `Settings` existente, sem duplicação de settings:

| Ambiente | Padrão | Efeito |
|---|---|---|
| `REDIS_URL` | ausente | Sem URL, cache desabilitado; Compose usa `redis://redis:6379/0`. |
| `GOLD_DATA_VERSION` | ausente | Identificador explícito e não vazio do snapshot. |
| `CACHE_TTL_SECONDS` | `300` | Inteiro positivo, expiração no SET. |
| `CACHE_TIMEOUT_SECONDS` | `1` | Positivo e finito, por GET/SET. |

Com URL e versão ausente/em branco, a inicialização falha por configuração
inválida, conforme o contrato existente. TTL/timeout inválidos também são
rejeitados quando habilitado. Sem URL, não se exige versão.

Antes de subir o Compose, defina a versão real do snapshot:

```powershell
$env:GOLD_DATA_VERSION = '2026-06-v1' # Exemplo; use a versão real.
docker compose up --detach --build --wait
```

Snapshot e versão devem ser atualizados juntos, com recriação do backend para
reler o ambiente. Não há hash completo do banco por requisição, versão baseada
apenas em mtime ou integração automática com a publicação do time de Dados.

## Chave, sessão e memória

```text
agent:answer:v2:<digest SHA-256>
```

JSON determinístico da pergunta normalizada pela C1, `session_id`, contexto
efetivamente encaminhado ao agente e versão Gold gera o digest. Não há nova
normalização, casefold ou compartilhamento entre sessões. Pergunta, memória e
sessão não aparecem em texto puro na key; o digest não autentica propriedade
de sessão. Mudanças incompatíveis de comportamento/contrato exigem revisão do
namespace; TTL não substitui versionamento.

O `RedisMemoryStore` agora é disponibilizado pela C7 quando há `REDIS_URL`.
Contexto recebido pelo parâmetro existente continua aceito; com sessão e store
configurados, o helper carrega a memória antes da chave e da geração.
Acrescentar uma interação muda o contexto e pode causar MISS no próximo pedido
da mesma sessão. Não se removeu o contexto da chave para aumentar HITs.

| Estado | Significado |
|---|---|
| `NOT_REQUESTED` | Sem contexto fornecido nem carregamento solicitado. |
| `EMPTY` | Memória carregada com sucesso, sem contexto útil. |
| `LOADED` | Contexto disponível. |
| `UNAVAILABLE` | Falha no carregamento/preparação da memória solicitada. |

Em `UNAVAILABLE`, não há GET, a chave fica `None` e não há SET. O pipeline
continua sem cache; o `RequestState` preserva a distinção entre falha e memória
vazia. `EMPTY` permite GET. A C2 não escreve memória.

## Payload e adapter

Somente `PostProcessingResult` é serializado: `answer`, `assumptions` e
`visualization`. Credenciais de configuração, pergunta, memória, SQL bruto,
request IDs e histórico de providers não são serializados.

O codec existente valida antes de gerar JSON e revalida com Pydantic estrito
no GET. Payload inválido/incompatível vira MISS, sem reparo ou migração.
`read_cache` também revalida retornos de stores injetados.

O adapter usa `redis.asyncio`, timeouts de conexão/comando e limite total via
`asyncio.timeout`, sem retries. Os helpers mantêm seus limites. Cancelamento
é propagado; logs incluem somente o tipo da exceção, sem URL, chave ou payload.
Referência: [cliente Redis](https://redis.io/docs/latest/develop/clients/redis-py/produsage/).

O HTTP atual usa `asyncio.run` por pergunta: cada operação abre e fecha seu
cliente/pool para não compartilhar conexões entre event loops. Não há conexão
ou PING obrigatório no startup/health do backend.

## Compose e persistência

`frontend → backend → redis:6379`, pela rede Docker. Gold em
`/data/gold/gold.db` RO e portal em `/data/portal/portal.db` RW preservados.
Somente frontend publica porta no host.

Redis usa healthcheck `redis-cli ping`, RDB/AOF desabilitados e `/data` em
tmpfs. Isso substitui o `VOLUME /data` da imagem e evita volume anônimo
persistente. Backend não tem `depends_on` para Redis e funciona sem ele.

## Validação executada

Na implementação inicial da C2, **254 testes locais passaram**, cobrindo chave/sessão/versão e contexto exato,
codec, configuração, adapter, GET/SET com exception/timeout, cancelamento,
MISS com SET, HIT sem etapas caras/SET, política de outcomes/completude,
memória indisponível, sessão HTTP e regressões de helpers/finalizer/pipeline/API.

No Compose real, versão `validacao-c2-local-v1` apenas para esta validação:

- Build/startup concluídos; backend/Redis saudáveis e frontend em execução.
- Primeiro pedido: MISS e SET; TTL observado de 300 segundos.
- Segundo pedido equivalente: HIT, outro request ID e nenhum novo SET.
- Contadores: GET=2, SET=1; geração, SQL Guardrail, executor, síntese,
  Output Guardrail e C6 executados uma única vez.
- Payload inválido e expiração real com TTL=1: MISS.
- Redis parado sozinho: backend permaneceu saudável, health HTTP retornou
  `ok` e duas respostas aprovadas foram entregues apesar dos timeouts de GET/SET.
- Redis religado: saudável e MISS/HIT confirmados novamente.
- Inspeção final: nenhuma porta Redis publicada ou volume persistente;
  mounts Gold RO e portal RW preservados.

Reprodução isolada da C2 (o script desabilita memória e auditoria somente no
ensaio para fixar o contexto), sem incluir testes na imagem:

```powershell
Get-Content -Raw backend/tests/manual/validate_redis_cache.py |
    docker compose exec -T backend python - healthy
docker compose stop redis
try {
    Get-Content -Raw backend/tests/manual/validate_redis_cache.py |
        docker compose exec -T backend python - offline
} finally {
    docker compose up --detach --wait redis
}
```

**Limite:** geração e síntese foram substituídas por funções determinísticas no
processo de validação. SQL Guardrail, executor SQL RO da Gold montada, Output
Guardrail, C6 e Redis foram reais. Não se comprovou conversa HTTP com providers
autenticados: o Compose não injeta suas credenciais. Gold/portal não foram
alterados; não houve FLUSHDB e o script remove apenas suas próprias chaves.

## Ainda fora da C2

- Memória Redis e auditoria persistente: implementadas pela [C7](C7-finalizacao.md).
- Logfire/instrumentação.
- Otimização de compartilhamento entre sessões e cache semântico.
- Publicação automática de `GOLD_DATA_VERSION` pelo pipeline de Dados.
