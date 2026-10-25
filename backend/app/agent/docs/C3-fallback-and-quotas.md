## Camada de Fallback e Quotas

### Decisões arquiteturais

A camada de acesso aos modelos de IA foi estruturada com **um provider principal e uma cadeia explícita de fallback**.

Fluxo definido:

```text
Gemini 3.1 Flash-Lite
        ↓ erro recuperável
Nemotron 3 Super
        ↓ erro recuperável
Nemotron 3 Ultra
        ↓ erro recuperável
Gemma 4
        ↓
PROVIDER_UNAVAILABLE
```

O **Gemini 3.1 Flash-Lite**, acessado diretamente pela API do Google, foi definido como provider principal.

O OpenRouter atua apenas como camada de contingência, utilizando, nesta ordem:

1. Nemotron 3 Super
2. Nemotron 3 Ultra
3. Gemma 4

O fallback é controlado pela própria aplicação através do `router.py`. Não utilizamos fallback automático do SDK ou do OpenRouter, permitindo maior controle sobre erros, tentativas e observabilidade.

### Tratamento de erros

Os providers convertem suas falhas para uma classificação comum através de `ProviderErrorType`.

Erros recuperáveis podem acionar fallback:

- `RATE_LIMITED`
- `PROVIDER_UNAVAILABLE`
- `TIMEOUT`
- `CONNECTION_ERROR`
- `INVALID_OUTPUT`

Quando a cota do Gemini é esgotada, o OpenRouter ainda pode ser utilizado, pois os dois providers possuem infraestruturas e limites independentes.

No OpenRouter, quando for identificado `QUOTA_EXHAUSTED`, a cadeia é encerrada imediatamente, pois trocar de modelo dentro do mesmo provider não resolveria o esgotamento global da conta.

Erros de configuração, autenticação ou requisição inválida não acionam fallback desnecessário.

### Retries

Retries automáticos foram desabilitados.

Cada modelo recebe apenas uma tentativa por passagem no fluxo. Caso ocorra um erro recuperável, o controle passa explicitamente para o próximo modelo.

Isso evita:

- latência imprevisível;
- consumo oculto de requisições;
- tentativas duplicadas;
- dificuldade de auditoria.

### Observabilidade

Cada tentativa de provider é representada por `ProviderAttempt`, contendo informações como:

- provider utilizado;
- modelo utilizado;
- posição da tentativa;
- timestamp;
- sucesso ou falha;
- latência;
- tipo de erro.

O uso do OpenRouter também é registrado localmente através do `usage_store.py`.

### Decisão sobre cota do OpenRouter

A aplicação **não tenta prever nem bloquear o uso com base em uma cota fixa**.

Isso foi decidido porque o limite real pode variar de acordo com a conta, créditos disponíveis e políticas do OpenRouter.

Portanto:

```text
usage_store
→ observa uso

OpenRouter
→ determina a disponibilidade real

router
→ reage ao erro retornado
```

Não existe mais lógica local de `NORMAL`, `WARNING` ou `CRITICAL`.

### Persistência temporária

Atualmente, as tentativas de uso do OpenRouter são persistidas em:

```text
.runtime/openrouter_usage.json
```

Essa persistência existe exclusivamente para observabilidade local.

O JSON é uma solução temporária e **não deve ser tratado como persistência definitiva da aplicação**.

### Alteração futura planejada

Quando a camada de persistência central do V-Energy Grid 360 estiver disponível, os registros de uso dos providers devem deixar o arquivo JSON e ser armazenados no banco de dados.

A migração deve preservar a separação entre:

```text
provider
model
timestamp
success
latency
error_type
```

Isso permitirá futuramente consultas, métricas e auditoria sem depender de arquivos locais.