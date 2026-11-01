# Guardrail de Entrada — V-Energy Grid 360

## Objetivo

A primeira camada de guardrail do agente foi criada para validar e proteger a entrada do usuário **antes de qualquer chamada ao modelo de IA**.

A proposta adotada foi manter essa camada **determinística, simples e barata**, evitando utilizar LLM para tarefas que podem ser resolvidas diretamente em Python.

O guardrail não tenta compreender profundamente a intenção do usuário. Questões semânticas mais complexas ficam para a etapa 4.1 do agente, já implementada com PydanticAI.

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

Ao bloquear, o pipeline preserva o mesmo `GuardrailReason` em
`PipelineResult.input_guardrail_reason`, sem expor esse campo na resposta HTTP.
Isso permite o futuro mapeamento central de outcomes/auditoria e distingue
`GUARDRAIL_INTERNAL_ERROR` de violações da entrada. Não há nova enumeração ou
persistência de auditoria nesta camada.

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
- normalização de tabs, quebras de linha e controles que representam whitespace;
- remoção dos demais caracteres de controle/invisíveis.

Separadores como `\r` são convertidos em espaço, sem juntar palavras:
`Qual\rfoi a receita?` vira `Qual foi a receita?`. A limpeza não reescreve termos
de negócio, mas a remoção de invisíveis ainda pode alterar emojis compostos.

### Limite de tamanho

Foi definido um limite de **500 caracteres após a normalização**.

Entradas maiores são bloqueadas e o usuário deve reformular a pergunta. O texto nunca é truncado silenciosamente.

O schema HTTP `PerguntaIn` não impõe tamanho mínimo nem repete esse limite no
texto bruto: entradas vazias e perguntas longas chegam à C1 para receber suas
mensagens. Há somente um **teto técnico de 16.384 caracteres brutos**, separado
do limite funcional, para limitar o trabalho de normalização. Acima desse teto,
ou quando o campo não é uma string válida, a API responde HTTP 422 antes da C1.

### SQL direto

O agente foi projetado para receber perguntas em linguagem natural.

São reconhecidas assinaturas comuns de SQL, sem parser completo:

- `SELECT ... FROM` com projeções compactas: colunas, `*`, funções simples,
  listas por vírgula, `DISTINCT` e aliases explícitos com `AS`;
- `INSERT INTO`;
- `UPDATE ... SET`;
- `DELETE FROM`;
- `DROP TABLE/DATABASE/VIEW`;
- `ALTER TABLE`;
- `CREATE TABLE/DATABASE/VIEW`;
- `TRUNCATE TABLE`.

Palavras isoladas como `SQL`, `SELECT` ou `tabela` não são suficientes para bloquear uma mensagem.
Inglês natural como `Select the municipalities from the last report and compare
consumption.` não é bloqueado apenas pela presença de `select/from`. A cobertura
é parcial: por exemplo, `SELECT 1` e `DROP INDEX` não são assinaturas desta camada.

### URLs

Links externos não possuem utilidade no agente atual, pois ele não acessará a web.

O reconhecimento atual cobre os prefixos `http://`, `https://` e `www.`, sem
diferenciar maiúsculas/minúsculas, e bloqueia com um retorno específico. Não é
um validador universal de URLs: domínios sem prefixo e outros protocolos, como
FTP, não são cobertos. Nenhum desses formatos é acessado pela C1.

### Prompt injection

A primeira camada identifica apenas padrões explícitos e facilmente reconhecíveis, como tentativas de:

- ignorar instruções anteriores;
- revelar o system prompt;
- redefinir explicitamente o papel do agente.

Não existe a intenção de detectar todo prompt injection por regex.

As assinaturas PT/EN reconhecem instruções anteriores/prévias, referências às
instruções do próprio agente/sistema, diretivas genéricas completas e mudança
explícita de papel. `Ignore as regras tarifárias antigas e compare a receita
por bairro.` é uma instrução de negócio e não corresponde a essas assinaturas.
A comparação ignora caixa e acentos, inclusive Unicode decomposto, sem retirar
acentos da pergunta encaminhada ao pipeline.

Essa detecção continua limitada a padrões explícitos. A classificação semântica
e as demais proteções pertencem às etapas posteriores; usar PydanticAI não é,
por si só, uma garantia de detecção de ataques sofisticados.

### Follow-ups e idioma

Não existe tamanho mínimo relevante além da necessidade de conteúdo alfanumérico útil.

Isso permite mensagens como:

```text
E Recife?
E em 2025?
Por bairro?
42
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

A etapa 4.1 concentra essa classificação e o Text-to-SQL; a C1 não adiciona uma
chamada extra de IA para classificação.

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
- short-circuit real: spies confirmam que regras posteriores não são chamadas;
- comportamento fail-closed na normalização e durante uma regra;
- follow-ups e limites bruto/normalizado pela interface HTTP;
- falsos positivos em inglês natural e regras tarifárias;
- injection sem acentos e com Unicode decomposto;
- motivo estruturado e encaminhamento da pergunta normalizada no pipeline.

Na revisão pré-E2E, passaram **203 testes**: 89 da C1, 10 de mensagens, 30 do
pipeline, 18 da interface HTTP da C1 e 56 da API existente. Os testes de
integração simulam as etapas posteriores, sem LLM ou acesso à Gold real.
