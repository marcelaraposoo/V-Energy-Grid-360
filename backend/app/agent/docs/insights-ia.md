# Insights de IA no portal

## Objetivo
Narrar, em linguagem de negócio, os insights que o portal já calcula, sem permitir que o modelo invente números. O código calcula; a IA só reescreve o texto.

## Fluxo
```text
services/ia.py: insights(repo, tela)
   │  calcula `dados` e um texto por regras (fiel por construção)
   ▼
rewriter.rewrite_insights(insights)
   │  1. remove dados pessoais de `dados` (uc_id, titular, endereço, cep...)
   │  2. pede ao modelo uma reescrita (1 a 2 frases, só valores de `dados`)
   │  3. valida o texto novo
   │  4. se falhar em qualquer passo, mantém o texto das regras
   ▼
list[Insight]  (mesmo contrato: tipo, texto, dados)
```

## Telas cobertas
| Tela | Insights |
|---|---|
| Fila e Ordens de Inspeção | Resumo da fila (unidades suspeitas, kWh/mês a recuperar, cobertura das primeiras 200 unidades); concentração por município |
| Visão 360 da UC | Consumo e fatura contra a referência; interrupções da UC (`GET /api/ia/insights/uc/{uc_id}`, regras em `uc_rules.py`) |

## Validação (determinística, sem IA)
- Todo número do texto novo deve existir em `dados` (tolerância de arredondamento; formato brasileiro e milhar ambíguo tratados). Datas e códigos como `AL025` não contam como números.
- Texto passa nas regras de texto da Camada 5: sem provedor/modelo, SQL, URL, vazamento de prompt ou erro técnico; máximo de 300 caracteres.
- Tipo (`alerta`, `destaque`, `informativo`) e `dados` nunca são alterados.

## Falhas e reserva
Timeout (12 s), erro de provedor, saída fora da validação ou qualquer exceção devolvem o texto original das regras. A tela nunca fica vazia.

## Privacidade
Chaves pessoais (`uc_id`, titular, documento, logradouro, número, cep, latitude, longitude) são removidas de `dados` antes de ir ao modelo. O conteúdo de `<dados>` é tratado como dado, nunca como instrução.

## Configuração
| Variável | Padrão | Efeito |
|---|---|---|
| `INSIGHTS_LLM` | `0` | `1` liga a reescrita; `0` mostra só o texto das regras (testes não chamam modelo) |

Os provedores e o fallback são os mesmos do agente (Gemini, Cohere, Nemotron conforme política de dados).

## Limitações
- O validador confere números, não o sentido: frase estranha com números corretos pode passar.
- Sem cache dos insights: a primeira abertura pode levar até o timeout. A chave sugerida é tela + hash dos dados (cache é da Camada 7).
- A reescrita é mais legibilidade que análise: não afirma causas nem recomendações.
- Formato: espaço antes de unidades e posição do sinal negativo podem variar.

## Testes
`tests/agent/test_insights_rewriter.py` (validação numérica, códigos de alimentador, chaves sensíveis, timeout, fallback, preservação de tipo e dados) e `tests/test_insights_uc.py` (rota da UC).

## Arquivos
`app/agent/insights/rewriter.py`, `app/agent/insights/uc_rules.py`, integração em `app/services/ia.py` e `app/routers/ia.py`.