# Revisão arquitetural do agente — 09/11/2026

Trabalho local na branch `ia/inteligencia-dominio-cache`, aplicado ao ambiente Docker. Este relatório complementa a [revisão de 08/11](revisao-agente-2026-11-08.md), que tratou dos timeouts SQL e das primeiras regressões. Não houve merge em `main`. As chamadas aos provedores configurados foram autorizadas pelo usuário; agregados e artefatos de avaliação permanecem em `backend/.runtime/`, ignorado pelo Git.

## 1. Diagnóstico arquitetural

O fluxo FastAPI → PydanticAI → guardrails → SQLite somente leitura → síntese → estado foi preservado. A revisão confrontou README, documentação do agente, contrato e dicionários Gold, serviços, navegação, componentes do assistente, configurações, testes e consultas à Gold real.

| Causa observada | Evidência | Alteração |
|---|---|---|
| Contrato limitado a gerar SQL | No baseline Docker, “O que significa DEC?” foi classificado como fora do domínio. | Contrato de intenção estruturada com rotas documental, analítica, híbrida e esclarecimento. |
| Memória mudava a chave após a própria resposta | Duas perguntas idênticas na mesma sessão produziram dois misses, duas chamadas de provedor em cada requisição e nova execução SQL. | Registrar o contexto antecedente à resposta e reutilizá-lo apenas em repetição imediata elegível. |
| Histórico confundia período pedido com cobertura parcial | A referência a 2025 podia herdar apenas janeiro–junho da resposta de 2026. | Período solicitado tipado e persistido; ano completo e cobertura encontrada são informações separadas. |
| Heurísticas de linguagem competiam com o modelo | O caminho anterior antecipava esclarecimentos e reinterpretações por expressões específicas. | O contrato real usa `InterpretedRequest`; heurísticas antigas ficam restritas à compatibilidade com adaptadores sem interpretação estruturada. |
| Referências em perguntas compostas mudavam de métrica | Em avaliação real, a definição de DEC foi acompanhada de faturamento, apesar de o usuário pedir o valor do indicador. | Uma revisão semântica independente, limitada, das perguntas híbridas, com schema recuperado pelas fontes selecionadas. |
| SQL válido podia calcular o indicador errado | Razão de somas anuais produzia média mensal de DEC/FEC, não acumulado anual. | Validação estrutural do grão antes da execução; numeradores/denominadores agregados por mês e soma dos índices mensais. |
| Resposta documental não tinha oportunidade de correção | Em uma rodada, o fallback gerou um número sem suporte e o guardrail bloqueou a resposta. | Uma correção documental limitada dentro do orçamento existente; segunda falha permanece bloqueada. |
| Correção conceitual ainda recebia contexto operacional irrelevante | Diagnóstico capturou uma explicação de consumo médio incluindo nome numérico do produto e datas do schema ausentes da fonte selecionada. | Retirar schema e cobertura da correção documental e exigir fundamentação nas fontes selecionadas; guardrail preservado. |

O baseline desta revisão foi o estado já corrigido em 08/11, não o código original do primeiro print. Os dois baselines não devem ser somados nem comparados como se fossem a mesma versão.

## 2. Domínio e fontes de verdade

A plataforma oferece Dashboard Executivo, Análise de Receita, Visão 360 da UC, Qualidade do Serviço, Fila/Ordens de Inspeção e Assistente IA. O portal possui operações sobre ordens; o assistente continua autorizado apenas a consultas e explicações. Recursos não confirmados nas fontes não devem ser anunciados como disponíveis.

`app/agent/context/knowledge.json` reúne seis fontes compactas: UC/rede; energia/consumo médio; continuidade; receita; atendimento/inspeções; recursos do portal. Cada fonte contém origem no repositório, fingerprint e tabelas relacionadas. O modelo escolhe IDs, e o backend recupera apenas IDs autorizados. Os testes detectam alterações nos documentos e no código de origem, exigindo revisão do texto curado antes do deploy. Não foram introduzidos serviço RAG, embeddings ou dependências.

Definições estáveis vêm dessas fontes. Cobertura, localidades e calendário vêm de metadados consultados em tempo de execução. Totais, rankings e variações vêm exclusivamente da Gold. Os fingerprints das fontes, do schema e dos prompts participam da identidade do cache. O catálogo carregado em memória é renovado com novo processo/deploy; o catálogo Gold é invalidado por tamanho e data de modificação do arquivo.

O contrato disponível inclui `dim_uc`, fatos de consumo/faturamento, interrupções, atendimento e trocas de medidor; agregado mensal por segmento; decomposição de receita; KPIs; DEC/FEC mensal por alimentador; fila de inspeção. O agente distingue consumo em kWh, energia faturada, receita faturada e recebimento/lucro, que não são intercambiáveis.

## 3. Componentes modificados

| Componentes | Responsabilidade |
|---|---|
| `schemas.py`, `sql_generator.py`, prompts SQL | Intenção, entregas, ambiguidades, fontes e período tipado antes do SQL. |
| `context/knowledge.py`, `knowledge.json` | Fontes curadas, validação de IDs, versionamento e recuperação de schema pertinente. |
| `context/runtime.py`, `context/geography.py` | Calendário/cobertura real, cadastro, normalização e resolução geográfica. |
| `semantic_plan.py`, `sql_execution_orchestrator.py` | Coerência de período/grão, revisão composta, correção documental, rollup equivalente e execução assíncrona segura. |
| `pipeline.py`, síntese e guardrail de saída | Rotas documentais sem SQL fictício; síntese híbrida com documentos e resultados separados; proveniência. |
| `state/cache_key.py`, `request_state.py`, `dependencies.py`, `finalizer.py`, memória | Identidade, repetição, invalidação, histórico estruturado e payload aprovado. |
| `providers/router.py`, `core/telemetry_export.py` | Preferência de modelo compatível com o novo schema; exportação restrita de métricas. |
| `services/ia.py`, `AuditoriaResposta.tsx` | Fontes documentais no contrato existente e explicação correta de cache/auditoria. |
| `benchmarks/domain_architecture.py`, testes do agente/estado/contratos | Avaliação HTTP real e regressões locais. |

Não foram criados endpoints nem campos obrigatórios na API pública. Não foram adicionados dados à Gold. As alterações da revisão anterior continuam na mesma árvore de trabalho e estão discriminadas no relatório de 08/11.

## 4. Interpretação semântica e execução

O modelo produz `SemanticIntent`: entregas solicitadas, ambiguidades, tipo, pergunta resolvida, métricas, localidades, período, filtros, agrupamentos, comparação, uso de contexto e fontes. Isso torna a interpretação inspecionável, em vez de selecionar respostas por palavras da pergunta.

- **Conceito/plataforma:** resposta fundamentada em fontes aprovadas, sem consulta analítica. Guardrails textuais e numéricos continuam ativos.
- **Análise:** proposta SQL validada contra leitura, whitelist, período e grão, seguida de execução e síntese.
- **Híbrida:** definição documental e valor calculado. Antes de executar, uma revisão usa o modelo alternativo já configurado e as seções de schema relacionadas aos IDs semânticos. Uma ambiguidade real continua pedindo esclarecimento.
- **Falta de contexto/fora do domínio/manipulação:** desfecho explícito; não autoriza consulta inventada.

Há no máximo uma revisão composta e uma correção de SQL/período/grão ou resposta documental, dentro do mesmo orçamento da fase. A síntese mantém sua política existente. Não há condicionais para “DEC em 2025”, Caruaru ou perguntas específicas do benchmark.

O otimizador troca uma soma no fato detalhado por `fato_segmento_mensal` apenas em formas comprovadamente equivalentes: medidas aditivas e dimensões compatíveis, sem joins, distinct ou filtros individuais de UC. Não reescreve média, contagem ou consulta arbitrária. Os testes com banco sintético comparam resultados das duas formas.

## 5. Cache e Redis

O processo Docker foi conferido diretamente: Redis no host de serviço `redis`, banco `/0`, PING bem-sucedido, versão Gold configurada e fonte SQLite. Esse é o Redis consumido pelo backend; não um servidor diferente na máquina hospedeira.

O primeiro lookup acontece depois da validação da entrada e recuperação da memória, antes de metadados, LLM, consulta analítica e síntese. A chave `agent:answer:v6` inclui pergunta normalizada, sessão/identidade disponível, contexto efetivo, data operacional, versão explícita Gold, tamanho/mtime do arquivo e versão das fontes/schema/prompts. O payload inclui texto aprovado, pressupostos, visualização, SQL de origem e interpretação/fontes.

Na repetição imediata, a memória só autoriza voltar ao contexto antecedente se ele foi explicitamente registrado para uma resposta bem-sucedida. Histórico legado, truncamento ou falha de memória não permitem reconstruir esse antecedente por adivinhação. Se a resposta expirar, a regeneração recebe o mesmo contexto. Uma mudança de turno relevante altera a identidade.

Há ainda lookup após gerar SQL, com plano canônico e escopo, pergunta e snapshot iguais. A interpretação estruturada também deve coincidir, exceto pelo sinalizador de uso de contexto. Isso evita reutilizar outra explicação híbrida só porque o SQL coincidiu.

Não foi implementado cache de paráfrases por similaridade. Mesmo planos equivalentes podem pedir explicações diferentes. A reutilização antecipada segura já elimina o custo da repetição literal; consultas agregadas são muito mais baratas que chamadas LLM. Não há evidência que justifique novo serviço vetorial neste escopo.

TTL da resposta: 24 h, sem renovação no GET, até 100 entradas por sessão. Respostas incompletas, erros, timeouts, esclarecimentos e ausência de dados não são armazenados. Falhas Redis não viram hits; falha ao recuperar memória impede reutilização dependente dela. Arquivo Gold indisponível ganha versão distinta, evitando resposta antiga sob identidade de arquivo disponível. Publicações continuam exigindo atualizar `GOLD_DATA_VERSION`; tamanho/mtime não substituem um identificador confiável de publicação.

**Evidência antes/depois:** no baseline, repetição de consumo de Recife teve `cache_hit=false`, duas chamadas de provedor e 3.548,54 ms na API. Na rodada anterior à última correção documental, as repetições de DEC e consumo tiveram hit, zero tentativas de provedor e nenhuma etapa C4.3 concluída, em aproximadamente 33 ms por HTTP. As medições finais constam na seção 9. SQL mostrado em hit é proveniência, não uma execução nova.

## 6. Localidades e Caruaru

Consulta direta em modo somente leitura confirmou 14 municípios no cadastro: Abreu e Lima, Araçoiaba, Cabo de Santo Agostinho, Camaragibe, Igarassu, Ilha de Itamaracá, Ipojuca, Itapissuma, Jaboatão dos Guararapes, Moreno, Olinda, Paulista, Recife e São Lourenço da Mata. `SELECT COUNT(*) FROM dim_uc WHERE municipio = 'Caruaru'` retornou **0**. Isso demonstra ausência de cobertura nesta base, não inexistência da cidade.

O resolvedor compara nomes sem diferenças de caixa, acentos e espaços; confirma pares município/bairro e normaliza os literais SQL para a grafia cadastral. Correspondência aproximada gera sugestão/esclarecimento, nunca troca silenciosamente de cidade. Bairro único pode estabelecer seu município, como Macaxeira/Recife. Entidade não mencionada ou troca de município pela SQL é rejeitada para esclarecimento.

Falhas de leitura do catálogo produzem erro técnico. Cadastro parcial, bairro ambíguo, localidade não coberta e consulta sem registros são estados distintos. O catálogo é limitado a 5.000 pares e prazo de 2 s; truncamento é informado. A resolução não usa uma API geográfica externa para afirmar existência de municípios fora da base.

Cobertura de competências confirmada por `MIN/MAX(mes_referencia)` em `kpis_mensal`: **julho/2022 a junho/2026**. A ausência de consumo de Macaxeira em outubro/2026 foi validada como `no_data`. Zero legítimo permanece diferente de medida nula/ausente.

## 7. Memória e isolamento

A memória Redis usa namespace `agent:memory:v2`. Armazena até 20 turnos, envia até cinco turnos e 4.000 caracteres ao modelo, priorizando os mais recentes. TTL renovável de 24 h. O histórico inclui a intenção resolvida e separa período pedido de cobertura observada.

A avaliação HTTP mantém a mesma sessão na sequência Recife/2026 → repetição → ano passado → Olinda → comparação. Os resultados são confrontados com SQL independente. Uma sessão nova recebendo apenas “E no ano passado?” pede esclarecimento. Os testes do frontend verificam que “Nova conversa” muda o UUID e ignora respostas pendentes da sessão anterior.

Cache e memória têm responsabilidades diferentes. Não há login nem comprovação de ownership do UUID na API atual: existe separação por identificador de conversa, não controle individual de autorização. A revisão não declara isolamento multiusuário autenticado que a plataforma ainda não implementa. Redis no Compose é volátil; reinício pode perder cache e memória, sem perder a Gold.

## 8. Auditoria, Logfire e desempenho

A resposta registra request ID, desfecho, tempos, tentativas por provedor/modelo, regenerações, metadados, intenção, fontes, resolução geográfica, plano, SQL e persistência. Respostas documentais não inventam execução. Hits preservam origem e têm auditoria própria. A persistência SQLite continua best effort: falha em salvar é visível, não mascarada como sucesso.

Logfire está habilitado e possui token configurado no ambiente em execução. Os testes com exporter em memória verificam spans, correlação e sanitização. A exportação admite métricas, enums e identificadores; remove perguntas, SQL, respostas, histórico, conteúdo de exceções e atributos não autorizados. **Não foi inspecionado o painel externo do projeto Logfire**, portanto configuração/testes locais não são apresentados como confirmação visual de ingestão.

Orçamentos preservados: 30 s para interpretação/SQL, 20 s para síntese, 10 s de execução SQLite; primário até 8 s e demais tentativas até 20 s, subordinados ao orçamento da fase. A revisão híbrida acrescenta uma chamada somente no caminho composto. A correção documental só ocorre quando o guardrail exige. Nenhum timeout foi aumentado.

As auditorias discriminam validação de entrada, cache/memória, metadados, entidades, interpretação, execução, síntese e tentativas de fallback. Uma rodada intermediária chegou a 25,56 s ao combinar indisponibilidade Gemini, timeout OpenRouter e fallback. Essa cauda de latência depende dos provedores e continua sendo uma limitação real; médias de consultas rápidas não a escondem.

## 9. Testes, avaliação e reprodução

| Verificação | Resultado |
|---|---|
| Baseline local antes desta revisão arquitetural | 2.024 passaram; 19 integrações LLM opt-in puladas |
| Backend após revisão e correção documental | **2.071 passaram; 19 puladas**, 48,63 s |
| Regressões após restringir o contexto da correção documental | **57 passaram**, 13,63 s; domínio e observabilidade |
| Frontend, incluindo sessão/Nova conversa/auditoria | **112 passaram**, zero falhas |
| Build frontend TypeScript/Vite e imagens Docker | Concluídos; backend/Redis saudáveis e frontend iniciado |
| Avaliação HTTP final com Gold, Redis e provedores reais | **27/27 cenários aprovados**; auditoria salva nas 27 requisições |
| Verificação final do ambiente | `/assistente`: HTTP 200; `/api/health`: `ok`, fonte `sqlite`; `git diff --check` sem erros |

Na rodada final, a mediana HTTP foi **3,01 s** e o máximo **22,89 s**. Houve **43 tentativas de provedor**, incluindo duas rejeições por limite de taxa, duas saídas inválidas e um timeout de tentativa; o fallback recuperou esses casos. Nenhuma requisição terminou em erro técnico. Isso não apaga as falhas das rodadas intermediárias nem garante que o provedor estará sempre disponível.

| Caso final | HTTP | Duração API | Chamadas de provedor | Execuções SQL | Cache |
|---|---:|---:|---:|---:|---|
| Explicar DEC, primeira vez | 2.802,42 ms | 2.737,47 ms | 1 | 0 | Miss |
| Repetir DEC | **62,80 ms** | **13,99 ms** | **0** | **0** | **Hit** |
| Consumo de Recife/2026, primeira vez | 5.691,13 ms | 5.596,65 ms | 2 | 1 | Miss |
| Repetir consumo de Recife/2026 | **57,47 ms** | **7,41 ms** | **0** | **0** | **Hit** |
| Explicação e maior FEC municipal/2025 | 22.890,97 ms | 22.828,21 ms | 6, incluindo fallback | 1 | Miss |
| Explicação e DEC da empresa/2025 | 8.777,01 ms | 8.728,62 ms | 4 | 1 | Miss |

Correlação das repetições: DEC `46520b01601349b0ad0e3eac1aceeca1`; Recife `a60ce7542b1942e0a687941f11162260`. Os registros apresentam `cache_hit=true`, lista vazia de tentativas e C4.3 não executada. A diferença HTTP/API inclui transporte e finalização; não se deve interpretar as duas durações como a mesma medida.

As regressões cobrem: fonte desconhecida; doc alterado; rota documental sem SQL; híbrida com fonte selecionada; correção limitada e bloqueio persistente; períodos e grão; equivalência do rollup; geo normalizada, aproximação, ambiguidade, bairro único e erro técnico; repetição, mudança de contexto, expiração, invalidação de arquivo/data/fontes, Redis indisponível e segurança. Os testes existentes de guardrails, limites e falhas de provedores continuam passando.

O benchmark HTTP possui 27 cenários de conceitos, plataforma, consumo, paráfrases, acentos, erro de grafia, cobertura, ranking, perguntas híbridas, memória, cache, ambiguidade, fora do domínio e injection. Usa sessões novas por grupo, oráculos SQL de leitura independentes para valores escalares e verifica ausência de provedor/execução nos hits. A comparação entre municípios verifica presença das entidades; os valores foram também revisados no resultado. A avaliação automática de conceitos verifica rota/fontes/ausência de SQL, complementada por leitura das respostas; não é uma prova automática de correção semântica de toda frase.

As rodadas intermediárias ficam preservadas: `arch_baseline_http.json` (baseline); `domain_http_release.json` (26/27, erro de métrica híbrida); `domain_hybrid_final.json` (duas híbridas corretas após revisão independente); `domain_http_final.json` (26/27, bloqueio documental após falhas de provedor); `domain_http_verified.json` (26/27, correção documental ainda exposta ao schema). **`domain_http_delivery.json` é a rodada final de 27/27**. `documentary_tests.txt` e `frontend_final_tests.txt` guardam os resultados locais. Um arquivo intermediário com erros HTTP enquanto Docker estava parado não foi contado como avaliação do modelo.

Reprodução a partir da pasta `backend`, com Docker saudável:

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=.runtime/pytest_review
.venv/Scripts/python.exe -m benchmarks.domain_architecture --allow-provider-calls --gold ../data/gold/gold.db --output .runtime/avaliacao_dominio.json
```

O segundo comando envia perguntas/metadados/agregados aos provedores configurados; a flag é opt-in. Não versionar os JSON de saída. Medições são observações locais, não SLA nem estimativa estatística de qualidade geral.

### Matriz de cobertura da seção 5.3

Referência verificável: P10/P11 em `docs/gold_contract.md`. As linhas abaixo decompõem esses requisitos para avaliação; não atribuem novos códigos oficiais ao case.

| Aspecto | Situação | Evidência e limite |
|---|---|---|
| P10: português, consumo/faturamento/interrupções/atendimento | Implementado no domínio documentado | Gold e testes de contrato/execução; a rodada nova não mede toda variação de atendimento. |
| Termos cotidianos e compreensão contextual | Validado na amostra | Sinônimo, informalidade, acentos, referências anuais e entre municípios; linguagem livre continua probabilística. |
| Conceitos e funcionalidades reais | Implementado e testado | Fontes curadas com origem e fingerprints, rota sem SQL; revisão humana ainda necessária ao atualizar fontes. |
| Valores e ausência de conhecimento | Implementado e testado | SQL independente, guardrails, desfechos de cobertura/ambiguidade/falha distintos; não é prova geral de toda consulta. |
| Memória e cache | Validado localmente e por HTTP/Redis | Hits comprovados, contexto e isolamento por sessão; falta ownership autenticado. |
| Auditabilidade e observabilidade | Implementado; validação externa parcial | Auditoria API/SQLite, spans e sanitização testados; painel Logfire não inspecionado. |
| Segurança | Guardrails preservados no escopo testado | SELECT/whitelist/read-only, limites, injection e proteção da saída; não equivale a auditoria de segurança exaustiva. |
| Integração do portal | Validada por testes/build/HTTP | Contrato público preservado; não foi feita nova inspeção visual manual do navegador. |
| P11: insights em pelo menos uma tela | Já implementado; cobertura de telas parcial | Integrações existentes em Visão 360/inspeção; expansão para todas as telas não fez parte desta revisão. |
| Avaliação repetível | Implementada | Suíte local e benchmark HTTP opt-in; amostra pequena, sem promessa de acerto universal. |

## 10. Pendências reais e teste pelo usuário

- LLMs continuam podendo interpretar mal uma formulação nova. Validações estruturais, fontes e revisão composta reduzem risco; não provam equivalência semântica de qualquer SQL com qualquer pergunta.
- Fallback pode levar dezenas de segundos. Erros sem fonte permanecem bloqueados mesmo após a correção limitada; não há resposta inventada para aparentar disponibilidade.
- O arquivo Gold termina em junho/2026 e não cobre Caruaru. A aplicação não passa a ter dados ausentes por melhorar a interpretação.
- Não há ownership autenticado das sessões, confirmação externa da ingestão Logfire, nem nova inspeção visual manual do navegador.
- Fora do Docker, a configuração local encontrada usa `DATA_SOURCE=mock`, caminho padrão sem esta Gold e sem Redis. Para repetir o ambiente validado, use o Compose ou configure explicitamente Gold/Redis/versão.
- Alterações permanecem locais; integração em `main` segue PR com uma revisão, conforme `AGENTS.md`.

Acesse `http://localhost:8080/assistente` e clique em **Nova conversa**. Perguntas sugeridas:

1. “O que significa DEC?” — definição com fonte documental, sem SQL.
2. “Qual o consumo total de Recife em 2026?” — valor consultado e cobertura parcial explícita. Repita exatamente para conferir hit e ausência de novas tentativas de provedor na auditoria.
3. Na mesma conversa: “E no ano passado?”, “Agora em Olinda.” e “Compara os dois municípios nesse ano.”
4. Em nova conversa: “O que é DEC e qual foi o valor da empresa em 2025?” — definição e DEC anual, não receita.
5. “Faturamento de Caruaru” — informa falta de cobertura, sem inventar valor.
6. Em nova conversa, só “E no ano passado?” — pede o assunto, sem herdar Recife.

Abra **Auditoria dessa resposta** para conferir fontes, intenção, SQL de origem, cache e tentativas. O código antigo do print não identifica sozinho a veracidade de um número; a comprovação vem da consulta e do período registrados.
