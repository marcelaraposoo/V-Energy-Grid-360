# Camada 6 — Pós-processamento e Visualização Analítica

## Objetivo

A Camada 6 prepara a resposta já aprovada pelo Output Guardrail para entrega ao frontend.

Ela também pode gerar uma especificação opcional de visualização analítica a partir do resultado real da consulta SQL.

A camada é totalmente determinística e não realiza chamadas a modelos de IA.

---

## Posição no fluxo

```text
4.3 Execução SQL
        │
        ├─────────────── QueryExecutionResult
        │
        ▼
4.4 Síntese
        ▼
5 Output Guardrail
        ▼
6 Pós-processamento
        ▼
7 Memória, Cache e Auditoria
```

A Camada 6 utiliza duas informações:

- a resposta textual produzida pela Camada 4.4 e aprovada pela Camada 5;
- o `QueryExecutionResult` produzido pela execução da consulta.

---

## Responsabilidades

A Camada 6:

- preserva a resposta textual aprovada;
- preserva as premissas da síntese;
- analisa a estrutura do resultado da consulta;
- decide deterministicamente se existe uma visualização adequada;
- produz um `VisualizationSpec` quando possível;
- retorna `visualization=None` quando não houver visualização segura.

A Camada 6 não:

- chama LLM;
- reescreve a resposta;
- extrai dados numéricos do texto produzido pela IA;
- executa SQL;
- gera imagens;
- renderiza gráficos;
- expõe SQL, provider ou modelo ao usuário.

---

## Fonte da verdade

Os dados utilizados para construir gráficos vêm exclusivamente de `QueryExecutionResult`.

A resposta textual da síntese não é utilizada como fonte de dados para visualizações.

Exemplo:

```text
Síntese:
"A receita foi R$ 9.999."

Resultado real:
Recife | 1000
Olinda | 800
```

A visualização utilizará:

```text
Recife | 1000
Olinda | 800
```

e nunca o valor `9999` presente no texto.

---

## Tipos de visualização

A primeira versão suporta:

### BAR

Utilizado quando o resultado possui uma dimensão categórica e uma métrica numérica.

```text
municipio | receita
Recife    | 120000
Olinda    | 90000
```

Resultado:

```text
BAR
```

### LINE

Utilizado quando a primeira coluna representa uma dimensão temporal e a segunda uma métrica numérica.

```text
mes_referencia | receita
2026-01        | 120000
2026-02        | 130000
```

Resultado:

```text
LINE
```

---

## Quando não gerar gráfico

A camada retorna `visualization=None` quando:

- não existem dados;
- existe apenas uma linha;
- existem mais de duas colunas;
- a métrica não é numérica;
- o resultado está truncado;
- o resultado possui mais pontos que o limite configurado;
- a estrutura não pode ser interpretada deterministicamente.

Não gerar uma visualização é um resultado válido e não representa erro.

---

## Limite de pontos

A primeira versão aceita no máximo 30 pontos.

Resultados maiores não são transformados automaticamente em gráficos, evitando visualizações ilegíveis e payloads desnecessariamente grandes.

---

## Contratos

### VisualizationPoint

```text
label
value
```

### VisualizationSpec

```text
type
title
x_label
y_label
unit
points
```

### PostProcessingResult

```text
answer
assumptions
visualization
```

`visualization` é opcional.

---

## Renderização

O backend não gera a imagem do gráfico. Ele apenas produz a especificação.

Exemplo:

```json
{
  "answer": "A receita cresceu no período analisado.",
  "assumptions": [],
  "visualization": {
    "type": "line",
    "title": "Evolução de receita por mes referencia",
    "x_label": "Mes referencia",
    "y_label": "Receita",
    "unit": "R$",
    "points": [
      {"label": "2026-01", "value": 120000},
      {"label": "2026-02", "value": 130000}
    ]
  }
}
```

O frontend é responsável por transformar essa especificação em um gráfico.

A interface pode apresentar a visualização de forma recolhida:

```text
Resposta do agente

▸ Visualizar gráfico analítico
```

O controle só é exibido quando `visualization` não for `null`.

---

## Segurança

A Camada 6 somente recebe respostas aprovadas pelo fluxo de síntese e Output Guardrail.

O `post_processing_orchestrator` verifica `SynthesisFlowResult.approved` antes de permitir o pós-processamento.

Respostas bloqueadas pelo Output Guardrail ou execuções com erro de provider não chegam à Camada 6.

---

## Arquivos

```text
app/agent/
├── schemas.py
├── post_processor.py
└── post_processing_orchestrator.py

tests/agent/
├── test_post_processor.py
├── test_post_processing_schemas.py
└── test_post_processing_orchestrator.py
```

---

## Evoluções futuras

Possíveis extensões:

- novos tipos de gráfico;
- múltiplas séries;
- melhores rótulos e unidades;
- ordenação específica por visualização;
- contratos de visualização mais ricos.

Essas extensões não fazem parte da primeira versão.
