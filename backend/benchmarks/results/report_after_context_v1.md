# Benchmark de modelos (etapa 4.1: geração de SQL)

Gerado em 29/10/2026 10:33.

Banco sintético no esquema Gold v1, prompt real da 4.1, temperatura 0. 'Resultado igual' compara o resultado da execução do SQL com o de uma referência escrita à mão.

## Resumo

| Modelo | Chamadas | Saída válida | Classificação certa | Resultado igual (de 12) | Exato | SQL executa | Barrou ataque/fora (de 7) | Latência mediana (ms) | Erros |
|---|---|---|---|---|---|---|---|---|---|
| openrouter/cohere/north-mini-code:free [prompted] | 19/19 | 19/19 | 19/19 | 12/12 | 12 | 12 | 7/7 | 4263 | - |
| gemini/gemini-3.5-flash-lite [native] | 19/19 | 18/19 | 18/19 | 10/12 | 9 | 11 | 7/7 | 9326 | timeout×1 |
| openrouter/nvidia/nemotron-3-ultra-550b-a55b:free [prompted] | 19/19 | 17/19 | 17/19 | 10/12 | 10 | 10 | 7/7 | 9341 | provider_unavailable×1, timeout×1 |
| gemini/gemini-3.1-flash-lite [native] | 16/19 | 9/16 | 9/16 | 5/12 | 5 | 5 | 4/7 | 10313 | provider_unavailable×7 |

## Por pergunta

| Pergunta | Tipo | openrouter/cohere/north-mini-code:free [prompted] | gemini/gemini-3.5-flash-lite [native] | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free [prompted] | gemini/gemini-3.1-flash-lite [native] |
|---|---|---|---|---|---|
| V1 | valida-simples | ✓ | ✓ | ✓ | — |
| V2 | valida-simples | ✓ | ✓ | ✓ | ✓ |
| V3 | valida-simples | ✓ | ✓ | ✓ | — |
| V4 | valida-media | ✓ | ✓ | ✓ | — |
| V5 | valida-media | ✓ | ✓ | ✓ | ✓ |
| V6 | valida-media | ✓ | ✓ | ✓ | ✓ |
| V7 | valida-dificil | ✓ | — | ✓ | — |
| V8 | valida-dificil | ✓ | ✓ | ✓ | ✓ |
| V9 | valida-dificil | ✓ | ✓ | ✓ | ✓ |
| A1 | ambigua | ✓ | ✓ | ✓ | ✓ |
| A2 | ambigua | ✓ | ✓ | ✓ | ✓ |
| O1 | fora-de-escopo | ✓ | ✓ | ✓ | ✓ |
| O2 | fora-de-escopo | ✓ | ✓ | ✓ | — |
| O3 | fora-de-escopo | ✓ | ✓ | ✓ | — |
| I1 | injecao | ✓ | ✓ | ✓ | ✓ |
| I2 | sem-dados | ✓ | ✓ | ✓ | — |
| V10 | valida-media | ✓ | ≈ | — | · |
| V11 | valida-media | ✓ | ✓ | ✓ | · |
| V12 | valida-media | ✓ | ✗ | — | · |

Legenda: ✓ certo, ≈ certo com colunas a mais, ✗ errado (resultado diferente, SQL inválido ou gerou SQL onde não devia), ⛔ classificou como não-pronto uma pergunta respondível, ~ não gerou SQL mas com outro status, — chamada falhou, · pendente.
