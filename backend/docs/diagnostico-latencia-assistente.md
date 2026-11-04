# Diagnóstico de latência e apresentação do Assistente IA

Investigação de **03/11/2026**, na branch `ia/observabilidade-logfire`.
Este documento registra evidências, limites do diagnóstico e mudanças recomendadas.
As otimizações e a visualização KPI descritas abaixo **não foram implementadas**.
C1–C7, guardrails, auditoria, memória, cache, ordem dos modelos e timeouts foram preservados.

## Origem das evidências

- Durações do trace HTTP de 62,1 s: informadas pelo usuário a partir do Logfire e da
  imagem de resumo. Não foram recuperadas pelo agente via Query API.
- Auditoria: consulta sanitizada ao `portal.db`, correlacionada à pergunta investigada.
- Formato do resultado: reexecução do SQL auditado, aprovado pela C4.2, com a Gold
  em modo somente leitura. Nenhum SQL, pergunta, resposta, sessão ou valor da Gold
  é reproduzido neste relatório.
- Contexto e tokens: tamanhos medidos no código em execução e contadores reportados
  pelo provider em um novo ensaio diagnóstico real.
- Validação funcional: testes existentes de síntese, C5, C6, contrato e privacidade.

## Trace HTTP de 62,1 segundos

| Operação | Duração aproximada | Interpretação |
| --- | ---: | --- |
| HTTP completo | 62,1 s | Tempo observado pelo usuário no Logfire |
| Geração SQL C4.1 | 38,2 s | Inclui as duas tentativas de provider abaixo |
| Primeiro provider da geração | 20,3 s | Log correspondente registra Gemini com `ModelRequestTimeout` |
| Segundo provider da geração | 17,9 s | Fallback que permitiu continuar a execução |
| Primeira síntese | 5,53 s | Resposta submetida à C5 |
| Segunda síntese | 17,2 s | Nova geração após a validação intermediária |
| Síntese + validação | Cerca de 22,7 s | Inclui as duas sínteses; não somar novamente ao HTTP |
| C7 | Cerca de 19 ms | Finalização não é o gargalo desse caso |

C4.1 representa aproximadamente 61,5% do total; síntese/validação, 36,6%.
Spans de provider são filhos das etapas: somá-los às durações das etapas contaria
o mesmo trabalho duas vezes.

A auditoria correlacionada tem request_id `9819776015864e36935b33130fc82c5a`,
outcome `answered`, cache MISS, uma linha, resultado não truncado e uma regeneração.
Ela foi finalizada às 15:13:50,531 de 03/11/2026, em America/Sao_Paulo.

### Timeout e variabilidade dos providers

O limite configurado é 20 s por chamada ao modelo. A medição de 20,3 s inclui
overhead do adapter e é compatível com esse limite. A categoria registrada foi
`timeout`, não autenticação ou quota. O fallback funcionou; ele acrescentou
17,9 s depois da tentativa inicial que não concluiu.

Não há medição suficiente de conexão, primeiro token, fila remota e processamento
para atribuir o atraso a um componente específico de rede ou do provider.
Os traces atuais não incluem instrumentação profunda de HTTPX/SDKs de rede.
O contexto grande é uma hipótese de contribuição, não uma causa isolada comprovada.

### Por que houve duas sínteses

O [orquestrador de síntese](../app/agent/synthesis_orchestrator.py) permite uma
regeneração quando a C5 bloqueia a resposta com `retryable=True` e há feedback
de correção disponível. Cada nova síntese inicia sua própria cadeia C3.

A sequência C4.4 → C5 → C4.4 e a única regeneração registrada são compatíveis com
esse ramo: a segunda chamada corrige a primeira resposta rejeitada. Isso é distinto
de fallback entre providers dentro de uma única C4.4. Um erro interno da C5 é
não recuperável e não dispara esse ramo.

**A regra exata do bloqueio histórico não foi preservada.**
[A projeção atual de metadados](../app/core/observability.py) exporta somente
`allow/block` na C5; `reason` e `retryable` não estão na whitelist atual.
A auditoria não armazena a primeira resposta rejeitada. Não é possível concluir
que o motivo foi número não suportado, SQL na resposta, número por extenso ou
outra regra apenas pelas durações. A resposta final aprovada não reconstrói a rejeitada.

## Tamanho do contexto e tokens

Tamanhos reconstruídos com a pergunta/SQL auditados, sem reproduzir seu conteúdo:

| Componente | Caracteres |
| --- | ---: |
| Schema Gold completo enviado à C4.1 | 20.759 |
| Instruções fixas da geração SQL | 9.407 |
| Total da geração, sem memória histórica ou feedback | 30.406 |
| Instruções fixas da síntese | 5.245 |
| Total da síntese histórica escalar, sem feedback | 5.632 |

O loader reutiliza o schema em memória, mas seu conteúdo completo continua entrando
no prompt a cada geração e fallback. Esse cache de arquivo não é cache de resposta
nem comprovação de cache de tokens no provider. A memória curta pode acrescentar
até 4.000 caracteres à geração; o conteúdo usado na requisição histórica não foi
reconstruído. A síntese envia no máximo 50 linhas; nesse caso havia apenas uma célula.
Feedback de regeneração aumenta o prompt da tentativa seguinte.

### Novo ensaio diagnóstico, sem otimização

Em processo diagnóstico separado, o pipeline original foi executado com providers,
Gold, guardrails e stores reais. A instrumentação temporária observou somente
metadados; não alterou decisões ou respostas das etapas.

- request_id: `2da3cf63ec2b4e399858ca4c7dd02882`.
- Pipeline: 6,147 s, `answered`, cache MISS, sem visualização.
- Nenhum fallback ou regeneração; C5 aprovou a primeira síntese.
- C7: aproximadamente 13 ms.

| Chamada | Provider/modelo | Latência do adapter | Tokens de entrada | Tokens de saída |
| --- | --- | ---: | ---: | ---: |
| Geração SQL | Gemini / `gemini-3.5-flash-lite` | 2,159 s | 9.097 | 107 |
| Síntese | Gemini / `gemini-3.5-flash-lite` | 1,443 s | 1.534 | 82 |

Os tokens são contadores das operações nativas `chat`, sem somar novamente os
agregados do agente. Não são os tokens do trace histórico de 62,1 s. Esse ensaio
usou sessão nova, memória vazia e nova geração de SQL; não é replay, medição HTTP
ou benchmark suficiente para justificar uma troca de modelo/timeout.
O mesmo contexto básico conseguiu concluir rapidamente: seu tamanho, sozinho,
não explica a latência histórica. A regra histórica da C5 não foi reproduzida.

## Resultados escalares e KPI

A consulta auditada retornou uma célula numérica completa; a reexecução confirmou
o valor agregado informado pelo usuário. A ausência de visualização é explicada
pelo contrato atual:

- [C6](../app/agent/post_processor.py) retorna `None` quando `row_count <= 1`.
  Os gráficos existentes exigem duas colunas, dimensão/métrica, e resultado completo.
- [VisualizationType](../app/agent/schemas.py) aceita apenas `bar` e `line`.
- O [tipo do frontend](../../frontend/src/api/types.ts) também aceita apenas esses formatos.
- O [renderer do Assistente](../../frontend/src/features/assistente/VisualizacaoChart.tsx)
  desenha linhas ou barras, sem ramo KPI.
- Existe [KpiCard](../../frontend/src/components/ui/KpiCard.tsx), usado em outras telas,
  que pode ser reutilizado numa futura integração ao Assistente.

Uma célula escalar deve ser apresentada como valor/KPI, sem inventar categorias,
histórico, percentuais de comparação ou séries para preencher um gráfico.

## Oportunidades por impacto e mudanças mínimas recomendadas

| Prioridade | Evidência e oportunidade | Próxima mudança mínima recomendada | Risco e limite |
| --- | --- | --- | --- |
| 1 | A tentativa inicial não concluída consumiu 20,3 s | Medir taxa de timeout e p50/p95 por modelo/fase; investigar rede/provider antes de propor outro timeout ou roteamento | Um limite menor pode descartar respostas válidas e aumentar fallback. Não há mudança aprovada de ordem ou timeout |
| 2 | A regeneração acrescentou uma chamada de 17,2 s | Adicionar motivo categórico validado, `retryable` e índice da validação aos metadados C5; depois corrigir o prompt conforme a regra comprovada | Não afrouxar C5 para evitar retries. Não exportar resposta rejeitada, `unsupported_values`, feedback ou exceções com conteúdo |
| 3 | A geração envia cerca de 30,4 mil caracteres sem memória | Experimentar compactação/seleção de contexto com testes de equivalência, mantendo segurança e contratos | Remover tabelas/relações pode piorar consultas multidomínio. O ganho de latência ainda não está demonstrado |
| 4 | C6 e o contrato não representam escalares como KPI | Acrescentar uma variante explícita `kpi` e renderização correspondente, preservando `bar`/`line` | Distinguir métricas de identificadores e manter compatibilidade com cache e payloads existentes |

A extensão da C5 exige atualização explícita da whitelist do exportador e testes
de privacidade. Exportar somente enum/booleano/índice, nunca conteúdo intermediário.

Para KPI, o valor deve vir exclusivamente do `QueryExecutionResult` completo e
não truncado. Exigir valor numérico finito e rejeitar booleanos; zero permanece zero,
e `null` não vira zero. Usar rótulo/unidade seguros derivados da métrica, sem extrair
o valor da resposta textual. Testar escalar, zero, nulo, identificador, truncamento,
gráficos existentes e serialização/validação de cache. Entradas antigas com
`visualization=None` podem continuar sem KPI até expirarem pelo TTL normal;
não apagar memória ou alterar a chave de cache para forçar a apresentação.

## Validação e pendências

Passaram **187 testes existentes** de síntese, C5, C6, contrato de visualização e
observabilidade. `git diff --check` passou. Não houve implementação de otimização,
alteração funcional ou mudança da política de privacidade nessa investigação.

Permanecem sem comprovação: a regra exata da C5 no trace histórico, seus tokens e
a divisão da latência entre rede/fila/processamento remoto. O token disponível ao
agente não permite consulta ao projeto Logfire (HTTP 401); a confirmação visual
do usuário e a aceitação OTLP são evidências distintas. A política de sessão e sua
pendência de ownership/autorização com DEV permanecem conforme
[C7 — Isolamento de sessão](../app/agent/docs/C7-finalizacao.md#isolamento-de-sessão--pendência-com-dev).

Para o incidente anterior de HTTP 504 e a espera de 300 s somente na rota de perguntas,
consultar [Dockerização — Espera do Assistente IA](../../docs/dockerizacao.md#espera-do-assistente-ia).
O trace de 62,1 s, o caso anterior de 43,1 s e o ensaio de 6,147 s são execuções diferentes.
