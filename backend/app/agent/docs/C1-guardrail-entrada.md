# Guardrail de Entrada — V-Energy Grid 360

## Objetivo

A primeira camada de guardrail do agente foi criada para validar e proteger a entrada do usuário **antes de qualquer chamada ao modelo de IA**.

A proposta adotada foi manter essa camada **determinística, simples e barata**, evitando utilizar LLM para tarefas que podem ser resolvidas diretamente em Python.

O guardrail não tenta compreender profundamente a intenção do usuário. Questões semânticas mais complexas ficam para a etapa 4.1 do agente, implementada posteriormente com PydanticAI.

---

## Estrutura criada nessa primeira fase

```text
app/
└── agent/
    ├── schemas.py
    ├── responses.py
    └── guardrails/
        ├── __init__.py
        ├── input_guardrail.py
        └── rules.py
```

Os testes foram organizados de forma semelhante:

```text
tests/
└── agent/
    ├── test_responses.py
    └── guardrails/
        └── test_input_guardrail.py
```

### `schemas.py`

Define os contratos internos utilizados pelo guardrail através de modelos Pydantic.

Foram definidos:

- `GuardrailDecision`: `ALLOW` ou `BLOCK`;
- `GuardrailReason`: motivo interno de um bloqueio;
- `InputGuardrailResult`: resultado padronizado da validação.

O resultado preserva tanto a entrada original quanto a versão normalizada.

### `rules.py`

Contém as funções determinísticas utilizadas pelo guardrail.

Responsabilidades atuais:

- normalização leve da entrada;
- identificação de conteúdo inválido;
- limite máximo de caracteres;
- detecção de SQL direto;
- detecção de URLs;
- detecção de padrões explícitos de prompt injection.

### `input_guardrail.py`

É o orquestrador da camada.

As regras são registradas de forma ordenada e executadas sequencialmente. O processamento utiliza **short-circuit**: assim que uma violação é encontrada, as próximas regras não são executadas.

### `responses.py`

Mantém separada a lógica de validação da comunicação com o usuário.

O guardrail retorna apenas códigos internos, como:

```text
DIRECT_SQL
INPUT_TOO_LONG
URL_NOT_SUPPORTED
```

O `responses.py` converte esses códigos em mensagens amigáveis.

---

## Decisões tomadas

### Perfil do guardrail

Foi adotado um guardrail de nível intermediário.

A camada realiza validações objetivas e baratas, mas não tenta substituir a capacidade semântica do agente.

### Limpeza da entrada

A normalização é propositalmente leve:

- remoção de espaços no início e no final;
- redução de whitespace repetido;
- normalização de tabs e quebras de linha;
- remoção de caracteres de controle/invisíveis.

A limpeza não reescreve nem altera semanticamente a pergunta.

### Limite de tamanho

Foi definido um limite de **500 caracteres após a normalização**.

Entradas maiores são bloqueadas e o usuário deve reformular a pergunta. O texto nunca é truncado silenciosamente.

### SQL direto

O agente foi projetado para receber perguntas em linguagem natural.

Por isso, SQL estruturalmente identificável é bloqueado, incluindo comandos como:

- `SELECT ... FROM`;
- `INSERT INTO`;
- `UPDATE ... SET`;
- `DELETE FROM`;
- `DROP`;
- `ALTER`;
- `CREATE`;
- `TRUNCATE`.

Palavras isoladas como `SQL`, `SELECT` ou `tabela` não são suficientes para bloquear uma mensagem.

### URLs

Links externos não possuem utilidade no agente atual, pois ele não acessará a web.

Mensagens contendo URLs são bloqueadas com um retorno específico.

### Prompt injection

A primeira camada identifica apenas padrões explícitos e facilmente reconhecíveis, como tentativas de:

- ignorar instruções anteriores;
- revelar o system prompt;
- redefinir explicitamente o papel do agente.

Não existe a intenção de detectar todo prompt injection por regex.

Ataques mais sofisticados serão tratados semanticamente no PydanticAI e também por outras camadas de segurança.

### Follow-ups e idioma

Não existe tamanho mínimo relevante além da necessidade de conteúdo alfanumérico útil.

Isso permite mensagens como:

```text
E Recife?
E em 2025?
Por bairro?
```

Também não há bloqueio por idioma. O comportamento de resposta em português será definido posteriormente no agente.

### Fail closed

Caso ocorra uma exceção interna no próprio guardrail, a entrada é bloqueada.

O motivo utilizado é:

```text
GUARDRAIL_INTERNAL_ERROR
```

Dessa forma, uma falha na camada de segurança não permite que uma entrada não validada avance no fluxo.

---

## Ordem das validações

```text
Entrada original
      ↓
Normalização leve
      ↓
Conteúdo útil?
      ├── NÃO → INVALID_INPUT
      ↓
Até 500 caracteres?
      ├── NÃO → INPUT_TOO_LONG
      ↓
SQL direto?
      ├── SIM → DIRECT_SQL
      ↓
Contém URL?
      ├── SIM → URL_NOT_SUPPORTED
      ↓
Prompt injection explícito?
      ├── SIM → PROMPT_INJECTION_PATTERN
      ↓
ALLOW
```

A primeira violação encontrada encerra o processamento.

---

## O que não pertence a esta camada

Foi decidido deixar para a etapa 4.1 do agente, utilizando PydanticAI:

- validação semântica do domínio V-Energy;
- identificação de perguntas fora de escopo;
- prompt injection sofisticado;
- intenção maliciosa não padronizável;
- pedidos de alteração de dados escritos em linguagem natural;
- interpretação de contexto e follow-ups;
- decisão de gerar ou não SQL.

A ideia inicial é que a mesma chamada responsável pelo Text-to-SQL também realize essa classificação semântica, evitando adicionar uma chamada extra de IA apenas para classificação.

---

## Testes

A camada foi validada com testes automatizados em `pytest`.

Foram testados, entre outros:

- perguntas válidas;
- follow-ups curtos;
- emojis;
- normalização;
- entrada vazia ou sem conteúdo útil;
- limite de 500 caracteres;
- SQL direto;
- vocabulário SQL sem comando;
- URLs;
- prompt injection explícito;
- prioridade das regras;
- short-circuit;
- comportamento fail-closed.

No fechamento desta etapa, **55 testes do Input Guardrail passaram com sucesso**, além dos testes do módulo de respostas.
