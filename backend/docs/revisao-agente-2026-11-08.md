# Revisão do agente — 08/11/2026

Alterações locais na branch `ia/revisao-semantica-agente`. A arquitetura FastAPI → PydanticAI → validação SQL → execução somente de leitura → síntese → validação da resposta → estado foi preservada.

## Diagnóstico com evidências

| Problema | Evidência | Correção |
|---|---|---|
| Timeout nas perguntas de consumo de Recife | Reproduzido com o código original isolado e a Gold real: execução SQL interrompida após 10,15 s e 10,41 s. A tabela mensal existia, mas estava excluída do contexto e da lista permitida. | Incluir `fato_segmento_mensal` no contrato físico, contexto e whitelist; preferir esse agregado para consultas compatíveis. |
| Follow-ups bloqueados mesmo com histórico | `requires_complete_question` era chamado antes da leitura da memória e novamente no gerador; o prompt de demonstração proibia completar referências. | Consultar memória primeiro; bloquear referências apenas sem contexto; resolver acompanhamentos no gerador existente. |
| Macaxeira desconhecida ou fora do domínio | O cadastro real contém o par Recife/Macaxeira. No baseline, o modelo pediu o município. A recusa fora do domínio do print não reapareceu nesse baseline, mas apareceu para outra localidade desconhecida durante a avaliação. | Metadados reais de localidades no contexto; uma recusa de pergunta operacional pode usar a única regeneração existente. Uma segunda recusa contraditória pede esclarecimento, sem autorizar SQL por palavra-chave. |
| “Mês passado” interpretado como mês anterior ao fim da Gold | Reproduzido durante a avaliação: o modelo escolheu maio/2026, embora a data de referência fosse novembro/2026. | Referência de calendário explícita, mês resolvido em código e verificação do filtro antes de consultar/cachear. Outubro/2026 não tem dados na Gold consultada. |
| `SUM(NULL)` classificado como sucesso | Reproduzido tanto com resultado inteiramente nulo como com uma soma nula acompanhada de rótulo literal de mês. | Identificar ausência de medidas no resultado e retornar `no_data`, sem síntese LLM; preservar zero legítimo. |
| Acompanhamento anual oscilava entre semestre e ano | Reproduzido: depois de pedir 2026 inteiro, “E no ano passado?” alternava entre janeiro–junho/2025 e 2025 inteiro. | Para essa referência inequívoca a um pedido anual explícito, resolver o ano anterior e validar o SQL. Comparação do “mesmo período” mantém tratamento separado. |
| Execução bloqueava o event loop | O executor síncrono era chamado diretamente dentro do fluxo assíncrono. | Executar SQLite em thread, mantendo as barreiras de leitura, timeout e limite de linhas. |
| Fallback podia consumir vários prazos completos | Os limites por fase já existiam, mas vinham desligados, inclusive no Compose. | Ativar os limites existentes de 30 s para a fase SQL e 20 s para síntese; não aumentar o timeout SQLite de 10 s. |
| Cache não distinguia mudança da data de referência | A chave incluía pergunta, sessão, memória e versão da Gold, mas não o calendário. | Incluir data de referência e alterar namespace para v4, invalidando respostas anteriores à revisão. |

Os timeouts reproduzidos foram de **execução SQL**, não de provedor. Não há evidência para atribuir os prints a quota ou indisponibilidade de modelo. Na última avaliação todas as chamadas bem-sucedidas usaram o Gemini já configurado; o fallback foi exercitado com mocks nos testes existentes.

## Comparação antes/depois com Gold e LLM reais

O baseline executou o código de `HEAD` anterior às alterações, copiado para um diretório isolado. As consultas usaram o mesmo arquivo `data/gold/gold.db`, aberto em modo de leitura. Tempos são observações locais, não SLAs.

| Pergunta | Antes | Depois |
|---|---|---|
| Qual o consumo de Recife em 2026 total? | Timeout SQL; requisição em 14,96 s | 46.176.660 kWh, explicitando janeiro–junho/2026; requisição em 4,68 s, SQL em 10,18 ms |
| Qual o consumo de Recife? | Timeout SQL; requisição em 12,36 s | 354.114.276 kWh, explicitando julho/2022–junho/2026; requisição em 5,17 s, SQL em 30,65 ms |
| Qual o consumo de Macaxeira mês passado? | Pedia município apesar do cadastro disponível | Resolve Recife/Macaxeira e informa ausência de dados em outubro/2026; requisição em 4,65 s |

A consulta de referência para o consumo anual foi:

```sql
SELECT SUM(consumo_kwh)
FROM fato_segmento_mensal
WHERE municipio = 'Recife'
  AND mes_referencia BETWEEN '2026-01' AND '2026-12';
```

O mesmo padrão, sem restrição de competência, fundamenta o total histórico. `MIN(mes_referencia)` e `MAX(mes_referencia)` fornecem os limites efetivamente disponíveis.

## Avaliação final e testes

A avaliação `benchmarks/semantic_regression.py` executa 10 cenários: consumo anual, acompanhamento anual, sinônimo “gastou de energia”, consulta sem período, bairro com período relativo, faturamento de Caruaru, ranking de interrupções, localidade ausente, fora do domínio e tentativa de manipulação/escrita.

Na última execução:

- **10/10 cenários aprovados pelos critérios definidos**, incluindo valores comparados com SQL independente, resposta textual e desfechos esperados.
- Reconhecimento de domínio: **8/8 perguntas operacionais**, indicador de triagem; não mede reconhecimento perfeito de toda entidade em linguagem livre.
- Recusas indevidas: **0/8**. Timeouts: **0/10**. Follow-up anual: **1/1**.
- Latência total observada: **2,20 a 5,87 segundos**. Durações por fase constam dos registros de auditoria.
- Auditoria SQLite persistida nas **10 requisições** da rodada final.
- Caruaru não está no cadastro desta Gold: o teste espera indisponibilidade/esclarecimento, não um valor inventado.

Testes executados:

| Verificação | Resultado |
|---|---|
| Suíte original do agente em snapshot isolado | 1.371 passaram, 32 pulados; 13 dos pulados dependem da Gold no caminho relativo daquele snapshot |
| Suíte completa do backend após as correções principais | 2.023 passaram, 19 integrações LLM opt-in puladas |
| Suíte do agente após o último ajuste de acompanhamento anual | 1.404 passaram, 19 integrações LLM opt-in puladas |
| Contrato físico, agregado sintético e regressões semânticas após atualizar o gerador sintético | 85 passaram |
| Configuração do Compose após alinhar os limites por fase | 2 passaram |
| Frontend, incluindo sessão, Nova conversa, auditoria e insights | 112 passaram |
| `git diff --check` | Sem erros de whitespace |

Os testes com fixtures e mocks não são evidência sobre valores da Gold real. A evidência real está nas consultas de leitura e na avaliação opt-in. Os resultados locais completos ficam em `.runtime/revisao_antes.json` e `.runtime/revisao_aprovada.json`, com os respectivos bancos de auditoria; não são versionados.

Durante uma rodada intermediária houve um timeout ao persistir a primeira auditoria SQLite. A falha foi exposta em C7; as 10 persistências da rodada final tiveram sucesso. A persistência continua sendo best effort, com prazo limitado: não há garantia de auditoria durável se o disco falhar.

## Arquivos e responsabilidades alteradas

| Arquivos | Justificativa |
|---|---|
| `app/agent/context/gold_schema_context.md`, `guardrails/allowed_tables.py`, fixtures de contrato/schema | Tornar o agregado mensal disponível, com grão, colunas e cuidados confirmados na Gold. |
| `app/agent/context/runtime.py` | Consultar localidades e cobertura em modo de leitura, limitar/cachear metadados e resolver datas relativas e a referência anual suportada. |
| `app/agent/intent_validation.py`, `sql_execution_orchestrator.py` | Reavaliar recusa operacional contraditória, validar os períodos e executar SQLite fora do event loop. Todas as correções compartilham o máximo de uma regeneração. |
| `app/agent/context_requirement.py`, `sql_generator.py`, `state/memory_context.py`, `pipeline.py` | Usar memória antes de esclarecer, evitar que repetição de pergunta incompleta crie contexto fictício e preservar auditoria de cada caminho. |
| `app/agent/result_semantics.py`, `answer_synthesizer.py`, `pair_check.py` | Separar ausência de medida, zero e localidade desconhecida; conservar evidências e tentativas ao pedir esclarecimento. |
| Prompts SQL e síntese | Sinônimos cotidianos, uso de catálogo, agregado preferencial, períodos explícitos e cobertura parcial. |
| `app/agent/state/cache_key.py`, teste manual Redis | Invalidar política anterior e distinguir data de referência, mantendo sessão, memória e versão da Gold. |
| `app/agent/execution_responses.py`, `app/core/config.py`, `compose.yaml` | Mensagem de timeout que não culpa a especificidade da pergunta; ativar os orçamentos existentes também no Compose. |
| `benchmarks/semantic_regression.py`, `build_synthetic_db.py` | Avaliação repetível com referências independentes; preencher o agregado sintético para não quebrar benchmarks anteriores. |
| `tests/agent/test_semantic_regression.py` e testes existentes ajustados | Cobrir casos novos, isolamento, dados ausentes, calendário, memória, segurança, contrato físico e equivalência do agregado. |
| Documentação C4.1 e `.env.example` | Atualizar contrato e explicitar a dependência de Redis para memória entre perguntas. |

Não foram adicionados provedores, dependências Python, endpoints ou campos obrigatórios na API pública. As barreiras SELECT/whitelist/`mode=ro`/authorizer e a validação numérica da resposta continuam ativas.

## Cobertura dos requisitos 5.3

| Requisito | Estado | Evidência e limite |
|---|---|---|
| RF-IA-01 — Linguagem natural | Implementado no escopo suportado | Pipeline completo com testes reais de consumo, faturamento/ausência de cobertura e interrupções; atendimento possui testes de contrato e execução, sem nova rodada LLM específica de atendimento. |
| RF-IA-02 — Linguagem cotidiana | Parcial | “Gastou de energia”, bairro e mês passado validados; a linguagem livre continua dependente do modelo. A verificação temporal determinística cobre os casos implementados, não toda expressão relativa possível. |
| RF-IA-03 — Auditabilidade | Implementado | Request ID, SQL, outcomes, tentativas, etapas, duração e persistência conferidos; a falha de persistência é visível. Logfire possui testes, mas não foi validado por envio a um projeto externo. |
| RF-IA-04 — Insights automáticos | Parcial | Infraestrutura já existente: números calculados em código, reescrita opcional validada e fallback. Renderização encontrada na Visão 360 e fila de inspeção; não há cobertura de todas as telas. |
| RF-IA-05 — Integração com o portal | Implementado | Contrato `/api/ia/perguntar` preservado e 112 testes frontend passando; não foi realizada nova validação visual em navegador. |
| RF-IA-06 — Segurança | Implementado no escopo testado | Guardrails de entrada/SQL/saída, bloqueio de escrita, teste de injection e Gold somente de leitura. Não equivale a uma auditoria de segurança exaustiva. |
| RF-IA-07 — Follow-ups | Parcial | Referência anual testada com LLM real, outras referências e isolamento com testes; produção precisa de Redis e contexto suficiente. Não há cobertura exaustiva de conversas longas ou ambiguidades entre múltiplos referentes. |
| RF-IA-08 — Avaliação automatizada | Implementado, amostra inicial | Script opt-in com oráculos SQL, desfechos, recusa indevida, timeout, follow-up e durações por fase. Dez cenários não estimam qualidade geral com confiança estatística. |

## Configuração e pendências reais

1. **Revisão e integração.** As alterações estão locais na branch de tarefa; não houve merge. Após solicitação do usuário, o ambiente Docker local foi reconstruído e iniciado com `docker compose up -d --build`. O fluxo do repositório exige PR para `main` com uma revisão.
2. **Desenvolvimento fora do Docker:** a configuração local encontrada usa `DATA_SOURCE=mock`, o caminho padrão `backend/data/gold.db` e não configura Redis. A Gold real está em `data/gold/gold.db`; para usá-la no processo local, configurar `SQLITE_PATH=../data/gold/gold.db`. O agente sempre consulta a Gold, independentemente da fonte mock das outras telas. A avaliação usou o caminho explícito, sem alterar credenciais/configurações privadas.
3. **Memória real entre requisições:** definir `REDIS_URL` e `GOLD_DATA_VERSION` quando executar fora do Compose. O Compose já configura Redis e monta a Gold correta. A avaliação de 10 cenários usou um MemoryStore isolado. Após subir o Docker, a memória Redis real também foi validada pela API: pergunta anual de Recife seguida de “E no ano passado?” na mesma sessão, com C2 passando de `empty` para `loaded` e auditorias salvas. Em nova sessão, o acompanhamento isolado pediu esclarecimento, sem herdar Recife.
4. **Nova conversa:** o frontend troca o ID da sessão e ignora respostas pendentes da sessão antiga. Isso separa contextos; os registros anteriores expiram pelo TTL. Não foi introduzido login nem exclusão automática de auditoria.
5. **Cobertura de dados:** o snapshot vai até junho/2026; perguntas sobre outubro/2026 devem retornar ausência de dados. Caruaru não consta no cadastro. Corrigir essas respostas não cria dados inexistentes.
6. **Insights:** contrato mínimo existente é `list[Insight]`, com `tipo`, `texto` e `dados`, em `/api/ia/insights?tela=...` e `/api/ia/insights/uc/{uc_id}`. Expandir outras telas e validar reescrita LLM ao vivo continua separado das correções prioritárias.

## Reprodução

Na pasta `backend`, com o ambiente Python instalado:

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=.runtime/pytest_review
.venv/Scripts/python.exe -m benchmarks.semantic_regression --gold ../data/gold/gold.db --output .runtime/avaliacao.json
```

O segundo comando usa provedores externos configurados e pode enviar metadados e agregados do case. A execução desta revisão teve autorização explícita do usuário. Os arquivos de resultados devem continuar em diretório ignorado.
