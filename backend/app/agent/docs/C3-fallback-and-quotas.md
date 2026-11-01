## Camada 3 — Providers, fallback e quotas

### Objetivo e ordem

A aplicação controla a cadeia em `providers/router.py`:

1. Gemini `gemini-3.5-flash-lite`;
2. OpenRouter `cohere/north-mini-code:free`;
3. OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free`, somente se permitido pela política de dados;
4. Gemini `gemini-3.1-flash-lite`, se diferente do principal e sem credencial Gemini invalidada.

Sucesso encerra a cadeia. Modelos repetidos no pool OpenRouter são deduplicados.
São no máximo quatro tentativas por passagem com a configuração atual, ou três
quando o Nemotron está desabilitado. Regenerações e síntese fazem novas passagens.

### Erros e credenciais independentes

`RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `TIMEOUT`, `CONNECTION_ERROR` e
`INVALID_OUTPUT` permitem tentar o próximo modelo.

`UNAUTHORIZED`, `FORBIDDEN` e `CONFIGURATION_ERROR` são tratados conservadoramente
como falhas do provider: pulam seus demais modelos, mas permitem o provider
independente. Uma dessas falhas no Gemini principal ainda permite OpenRouter,
mas impede repetir a credencial no Gemini final. No OpenRouter, encerra somente
o laço OpenRouter e permite o Gemini final.

`QUOTA_EXHAUSTED` no Gemini permite OpenRouter; no OpenRouter encerra somente
seu laço e permite o Gemini final. Quota não é inferida de todo HTTP 429:
o adapter preserva a classificação específica fornecida pelo SDK.
`BAD_REQUEST` e `UNKNOWN` encerram a cadeia inteira.

Se ninguém responder, `aggregate_errors()` considera todas as tentativas,
incluindo a final, nesta ordem de prioridade:

1. última falha terminal (`BAD_REQUEST` ou `UNKNOWN`), se existir;
2. `QUOTA_EXHAUSTED`, se qualquer tentativa identificar quota esgotada;
3. última falha efetiva da lista.

Assim, quota conhecida não é apagada por indisponibilidade ou falha de credencial
posterior. A lista completa permanece disponível para diagnóstico; o erro agregado
não pretende descrever sozinho todas as causas. Sucesso retorna erro agregado nulo.

### Timeout, retries e saída estruturada

O timeout é **20 segundos por chamada ao modelo**, via `request_timeout` do
PydanticAI. `max_retries=0` e retries de tools/output iguais a zero mantêm uma
tentativa por modelo por passagem. A aplicação não solicita uma lista de fallback
ao OpenRouter; isso não controla possíveis redirecionamentos entre upstreams
feitos pelo serviço dentro de uma chamada ao mesmo modelo.

**Não existe deadline global da requisição HTTP.** Seu orçamento e os timeouts
de cliente/proxy permanecem pendentes para o E2E. Os 20 s não incluem a soma
de fallback, regenerações, síntese e demais etapas.

Gemini usa `NativeOutput`; OpenRouter usa `PromptedOutput` com validação Pydantic
local, sem exigir `response_format` dos modelos gratuitos. Texto livre e JSON
incompatível quando se espera objeto estruturado resultam em `INVALID_OUTPUT`
e permitem fallback. Testes com o Agent real e `FunctionModel` local verificam
essas falhas, fallback e timeout sem consumir APIs externas.

### Tentativas e logs

`ProviderAttempt` preserva provider, modelo, ordem, timestamp, sucesso, latência
e categoria de erro. O router numera cada passagem; as interfaces consumidoras
acrescentam `phase=sql_generation` ou `phase=synthesis` e ordenam as tentativas
acumuladas, inclusive regenerações. O `PipelineResult.provider_attempts` reúne
as fases em ordem cronológica e preserva metadados em todas as saídas normais,
inclusive falhas. A fase pode ser nula na chamada direta ao adapter/router.
Falha de configuração antes da API também gera tentativa, com latência zero;
modelo pulado pela política não é uma chamada nem uma tentativa produzida.

Os metadados são internos, sem auditoria persistente ou Logfire. A resposta ao
usuário continua usando mensagens seguras. Logs próprios da C3 registram apenas
metadados técnicos, sem corpo/repr de exceções, causa bruta ou traceback.

### JSON local best-effort

`.runtime/openrouter_usage.json`, relativo ao diretório de execução, registra
somente timestamps UTC de tentativas OpenRouter em **janela móvel de 24 h**.
Não é contagem de sucessos, quota diária autoritativa ou mecanismo de bloqueio:
o provider continua sendo a fonte real de disponibilidade/cota.

O registro usado pelo adapter roda fora do event loop, com timeout de lock de
0,1 s e espera máxima de 0,25 s pela telemetria. Falha de diretório, leitura,
JSON, gravação ou lock significa somente perda de telemetria local e não impede
a chamada ao modelo. Há no máximo um trabalho de registro por processo; se
ocupado, registros novos são descartados, sem fila crescente. O timeout não
cancela I/O do SO já iniciado: o worker pode terminar depois, sem reter o loop.
As funções síncronas de manutenção/leitura continuam sendo helpers locais;
não devem ser chamadas diretamente pelo event loop.

O JSON pode desaparecer na recriação do container, pois não tem volume próprio.
Não foi migrado para Redis ou banco. Persistência central é trabalho futuro.

### Política de dados confidenciais

O [endpoint gratuito NVIDIA Nemotron](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free)
informa que não deve receber dados confidenciais ou pessoais. Os dados reais do
case são confidenciais: esse endpoint permanece **bloqueado por padrão**.

`PROVIDER_PAYLOAD_POLICY=confidential` é o padrão. Ausência, opção vazia ou
valor desconhecido também mantém a restrição. Somente o valor explícito
`synthetic` permite o endpoint, para testes cujo **payload inteiro** (pergunta,
contexto, memória e resultados) seja artificial. A opção declara a política do
payload; não inspeciona seu conteúdo nem anonimiza dados. Ter uma pergunta
sintética não torna um contexto extraído da Gold real sintético.

O router pula o modelo restrito sem substituí-lo, registrando a decisão técnica;
o adapter também bloqueia chamadas diretas antes de criar o modelo/enviar dados.
Os outros modelos conservam sua ordem. Essa restrição conhecida não é uma
aprovação de confidencialidade dos outros endpoints: a equipe ainda precisa
decidir quais providers/payloads reais são autorizados no E2E. Não liberar
`synthetic` para dados reais; eventual mudança dessa política requer decisão
explícita da equipe. Nesta tarefa, nenhum dado real foi enviado.
