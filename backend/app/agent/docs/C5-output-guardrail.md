# Camada 5 — Output Guardrail

## 1. Visão geral

A **Camada 5 — Output Guardrail** valida, de forma determinística, a resposta produzida pela 4.4 antes de ela ser exibida ao usuário.

A 4.4 usa um LLM e, por isso, pode escrever números que não estão nos dados, vazar instruções internas ou citar detalhes de infraestrutura. A Camada 5 é a barreira entre essa geração probabilística e o usuário.

Não utiliza LLM. Toda a validação é feita por código.

```text
4.3 — Execução SQL
        ↓
4.4 — Síntese da resposta
        ↓
Camada 5 — Output Guardrail
        ↓
ALLOW → exibe a resposta
BLOCK → uma regeneração → exibe ou mensagem segura
```

---

## 2. Responsabilidades

A camada é responsável por:

- bloquear resposta vazia ou longa demais;
- bloquear vazamento de prompts e instruções internas;
- bloquear nomes de providers e modelos de IA;
- bloquear stack traces e mensagens de erro técnicas;
- bloquear SQL (inclusive o SQL executado) e URLs no texto;
- **verificar que todo número citado tem origem nos dados**;
- indicar se o bloqueio permite uma nova tentativa;
- produzir feedback determinístico para uma regeneração;
- falhar de forma segura (fail closed).

Não é responsabilidade da camada:

- gerar ou corrigir a resposta;
- avaliar o sentido do texto (por exemplo, se "queda" ou "aumento" está correto);
- executar SQL ou controlar providers.

---

## 3. Ordem das validações

A primeira violação encerra o processamento (short-circuit). Segurança vem antes dos números.

```text
Resposta vazia ou sem conteúdo?        → EMPTY_ANSWER
Mais de 3.000 caracteres?              → ANSWER_TOO_LONG
Trecho de prompt ou instrução interna? → PROMPT_LEAK
Nome de provider ou modelo?            → PROVIDER_DISCLOSURE
Stack trace ou erro técnico?           → TECHNICAL_ERROR_LEAK
SQL (ou SQL executado) no texto?       → SQL_IN_ANSWER
URL?                                   → URL_IN_ANSWER
Número sem origem nos dados?           → UNSUPPORTED_NUMBER
        ↓
ALLOW
```

O texto da resposta e as suposições são verificados juntos.

---

## 4. Verificação numérica

### Leitura de números

O leitor interpreta o formato brasileiro (`4.820`, `1.234,56`, `12,5%`).

- Números ambíguos (`4.820` pode ser 4820 ou 4,82) guardam as duas interpretações; basta uma bater.
- Datas, marcadores de lista e identificadores (`B1`, `A4`) são ignorados.
- O sinal é ignorado.
- Formatos inválidos (`1.2.3`) são tratados como números sem origem.

### Números permitidos

| Fonte | Quando vale |
|---|---|
| Valores das linhas retornadas | Sempre (até 50 linhas, o que o modelo viu) |
| Números dentro de textos das células | Sempre |
| Números da pergunta e do SQL | Sempre |
| Ano e mês de datas | Sempre |
| `row_count`, linhas enviadas e posições | Sempre |
| Constantes 0, 1, 12 e 100 | Sempre |
| Soma, média, mínimo, máximo, contagem e participação no total (%) por coluna | **Só com resultado completo** |

Resultado completo significa: sem truncamento, `row_count` igual ao número de linhas e até 50 linhas.

### Tolerância

A comparação aceita meia unidade da última casa escrita: `79,6` aceita de 79,55 a 79,65.

### Fora do conjunto permitido

Diferenças entre linhas, variações entre períodos, medianas e projeções não são aceitas. O prompt da 4.4 lista exatamente o que o modelo pode derivar.

---

## 5. Regeneração

Se a resposta é bloqueada por um motivo corrigível, a 4.4 é chamada de novo **uma única vez**, com um feedback determinístico.

- `UNSUPPORTED_NUMBER` devolve ao modelo os valores rejeitados e a resposta anterior.
- Nos demais motivos, a resposta rejeitada **não** volta no feedback, porque pode conter o conteúdo que não deve ser repetido (prompt, SQL, erro técnico).
- Erro interno do guardrail não permite regeneração.

Se a segunda resposta também for bloqueada, o fluxo encerra e o usuário recebe uma mensagem fixa que não revela o motivo técnico (`output_responses.py`).

---

## 6. Resultado vazio

Resultado sem linhas gera uma mensagem fixa em código (`NO_DATA`) na 4.4 e **não passa pelo guardrail**, porque não contém texto gerado por IA.

---

## 7. Arquitetura

```text
app/agent/
├── guardrails/
│   ├── output_rules.py        # leitura de números
│   ├── allowed_numbers.py     # conjunto de números permitidos
│   ├── output_text_rules.py   # regras de texto
│   └── output_guardrail.py    # validação e feedback
├── output_responses.py        # mensagens seguras ao usuário
└── synthesis_orchestrator.py  # 4.4 + Camada 5 + 1 regeneração
```

O orquestrador expõe `SynthesisFlowResult.approved`: a resposta só pode ser exibida quando for `True`.

---

## 8. Decisões tomadas

- **Permissivo:** aceita somas, médias e porcentagens recalculadas em código, para a resposta ser útil sem perder verificabilidade.
- **Fail closed:** qualquer exceção bloqueia.
- **Sem LLM:** o guardrail é barato, rápido e previsível.
- **Feedback sem eco:** conteúdo sensível bloqueado não é reenviado ao modelo.
- **Nomes de modelos lidos da configuração:** a lista acompanha as trocas de modelo.

---

## 9. Limitações conhecidas

- Números por extenso ou abreviados (`mil`, `1,2 milhão`, `três`) não são reconhecidos. O prompt pede dígitos.
- O sinal é ignorado: a camada não distingue "queda de 5%" de "aumento de 5%".
- A camada confere números, não o sentido das frases.
- A palavra "system prompt" na resposta bloqueia, mesmo numa recusa educada.
- O limite de 50 linhas deve acompanhar `MAX_ROWS_IN_PROMPT` da 4.4 (há um teste que garante isso).
- Respostas fiéis podem ser bloqueadas por regras de texto agressivas (falso positivo). A afinação depende de testes com o modelo real.

---

## 10. Testes

### Determinísticos

- leitura de números (formatos, ambiguidade, datas, listas, identificadores);
- conjunto permitido (fontes, derivados, truncamento, tolerância);
- regras de texto e ordem de prioridade;
- fail closed, feedback e mensagens seguras;
- orquestrador (aprovação, uma regeneração, erro de provider, NO_DATA).

### Reais (`RUN_LLM_INTEGRATION=1`)

- total derivado de resultado completo;
- resultado parcial sem números inventados;
- instrução dentro dos dados;
- cálculo indisponível sem invenção de valor.

```powershell
$env:RUN_LLM_INTEGRATION="1"
python -m pytest tests/agent/integration/test_synthesis_flow_real.py -v -s
```

---

## 11. Pendências

- integrar o orquestrador à rota FastAPI, junto com a 4.3;
- testes adversariais mais amplos no benchmark;
- decidir se resultados de 50 a 500 linhas devem enviar mais linhas ao modelo.