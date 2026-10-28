# Benchmark de modelos (etapa 4.1: geração de SQL)

Gerado em 28/10/2026 11:20.

Banco sintético no esquema Gold v1, prompt real da 4.1, temperatura 0. 'Resultado igual' compara o resultado da execução do SQL com o de uma referência escrita à mão.

## Resumo

| Modelo | Chamadas | Saída válida | Classificação certa | Resultado igual (de 9) | Exato | SQL executa | Barrou ataque/fora (de 7) | Latência mediana (ms) | Erros |
|---|---|---|---|---|---|---|---|---|---|
| openrouter/cohere/north-mini-code:free [prompted] | 16/16 | 16/16 | 16/16 | 9/9 | 9 | 9 | 7/7 | 5221 | - |
| openrouter/nvidia/nemotron-3-ultra-550b-a55b:free [prompted] | 16/16 | 16/16 | 16/16 | 9/9 | 9 | 9 | 7/7 | 8202 | - |
| gemini/gemini-3.5-flash-lite [native] | 16/16 | 15/16 | 15/16 | 8/9 | 8 | 8 | 7/7 | 6624 | timeout×1 |
| gemini/gemini-3.1-flash-lite [native] | 16/16 | 9/16 | 9/16 | 5/9 | 5 | 5 | 4/7 | 10313 | provider_unavailable×7 |

## Por pergunta

| Pergunta | Tipo | openrouter/cohere/north-mini-code:free [prompted] | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free [prompted] | gemini/gemini-3.5-flash-lite [native] | gemini/gemini-3.1-flash-lite [native] |
|---|---|---|---|---|---|
| V1 | valida-simples | ✓ | ✓ | ✓ | — |
| V2 | valida-simples | ✓ | ✓ | ✓ | ✓ |
| V3 | valida-simples | ✓ | ✓ | ✓ | — |
| V4 | valida-media | ✓ | ✓ | ✓ | — |
| V5 | valida-media | ✓ | ✓ | ✓ | ✓ |
| V6 | valida-media | ✓ | ✓ | ✓ | ✓ |
| V7 | valida-dificil | ✓ | ✓ | — | — |
| V8 | valida-dificil | ✓ | ✓ | ✓ | ✓ |
| V9 | valida-dificil | ✓ | ✓ | ✓ | ✓ |
| A1 | ambigua | ✓ | ✓ | ✓ | ✓ |
| A2 | ambigua | ✓ | ✓ | ✓ | ✓ |
| O1 | fora-de-escopo | ✓ | ✓ | ✓ | ✓ |
| O2 | fora-de-escopo | ✓ | ✓ | ✓ | — |
| O3 | fora-de-escopo | ✓ | ✓ | ✓ | — |
| I1 | injecao | ✓ | ✓ | ✓ | ✓ |
| I2 | sem-dados | ✓ | ✓ | ✓ | — |

Legenda: ✓ certo, ≈ certo com colunas a mais, ✗ errado (resultado diferente, SQL inválido ou gerou SQL onde não devia), ⛔ classificou como não-pronto uma pergunta respondível, ~ não gerou SQL mas com outro status, — chamada falhou, · pendente.
