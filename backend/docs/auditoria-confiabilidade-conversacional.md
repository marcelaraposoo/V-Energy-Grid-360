# Auditoria de confiabilidade conversacional

Diagnóstico de 04/11/2026 UTC. Nenhuma correção de produção foi implementada.

## Método e limites

- Auditoria do portal.db aberta com SQLite mode=ro; consultas na Gold somente leitura.
- Sem chamada LLM, acesso/modificação ao Redis, atualização de containers ou mudança de timeout.
- Os arquivos de memória, domínio, contexto Gold e C5 analisados correspondem por hash aos do container.
- Não existem snapshots do prompt nem das linhas históricas na auditoria. O histórico abaixo foi reconstruído dos outcomes elegíveis; isso não comprova que Redis entregou exatamente esse texto naquela requisição.
- Reexecuções conferem o snapshot Gold atual. Não são captura retrospectiva dos resultados originais.
- Não foram exportados perguntas/respostas da auditoria, SQL completo, IDs de sessão, credenciais ou linhas individuais da Gold.

## 1. DEC para últimos seis meses

**Evidência:** na mesma sessão houve primeiro timeout de provider e depois um follow-up com NEEDS_CLARIFICATION. PROVIDER_ERROR não entra na memória C7; naquele momento a reconstrução não tinha uma resposta DEC válida. Mais tarde houve ANSWERED com ranking DEC e outro follow-up NEEDS_CLARIFICATION sobre município/interrupções. A reconstrução desse segundo caso contém a pergunta DEC e o esclarecimento anterior, em 1.012 caracteres, abaixo do limite.

**Classificação:** primeiro episódio tem ausência de âncora válida após falha; segundo é perda de interpretação na C4.1, possivelmente influenciada pelo esclarecimento anterior. Não há prova de falha de persistência Redis. C7 conserva até 20 turnos; o prompt usa até cinco e 4.000 caracteres. O serializador envia pergunta/resposta, sem distinguir ANSWERED de NEEDS_CLARIFICATION. Entradas grandes são descartadas integralmente.

**Menor correção candidata:** explicitar o status já disponível no histórico; distinguir último assunto validado de esclarecimento pendente; instruir alterações parciais de período a preservar métrica, dimensão e ordenação. Nenhuma regra especial para DEC ou para esta frase.

**Riscos/testes:** não confundir mudança deliberada de assunto com acompanhamento; verificar âncora anterior, ausência de âncora, esclarecimento incorreto intermediário, contexto longo e período absoluto resolvido. Só teste de prompt não comprova obediência do modelo.

## 2. Substituição DEC por FEC

**Evidência:** NEEDS_CLARIFICATION, sem SQL; histórico reconstruído de 1.176 caracteres ainda contém DEC e o pedido anterior de seis meses, além dos esclarecimentos. O gerador recebe o histórico como texto livre, sem contrato de intenção resolvida.

**Classificação:** C4.1; provável propagação da deriva do caso 1. A C5 não executa quando a geração pede esclarecimento.

**Menor correção candidata:** aplicar mudança de métrica sobre a última intenção válida e reter período, filtros, dimensão e ranking quando compatíveis. Se a intenção anterior estiver incompleta, esclarecer somente a lacuna, sem exigir todos os campos outra vez.

**Riscos/testes:** preservar somente filtros compatíveis com a nova métrica. Avaliar DEC12 → DEC6 → FEC6, com e sem esclarecimento intermediário, além de mudança explícita de município/assunto.

## 3. Gastos interpretados como faturamento

**Evidência:** a execução selecionou receita_total de kpis_mensal e retornou três linhas. A reexecução foi bem-sucedida e os números da resposta passaram na validação numérica atual. O domínio já proíbe equiparar gastos/despesas a receita e já determina esclarecimento sem definição do usuário; uma resposta anterior do assistente não constitui definição.

**Classificação:** erro de interpretação na C4.1 apesar da instrução existente. Não há evidência de números inventados neste registro: existem registros de faturamento que sustentam os números, mas isso não resolve a ambiguidade financeira. A C5 valida números, não a escolha semântica da métrica.

**Menor correção candidata:** acrescentar uma decisão verificável de métrica/perspectiva financeira antes de autorizar READY, confrontando o pedido resolvido, o glossário e a AST SQL. Não basta acrescentar sinônimos ou repetir mais vezes a mesma instrução; declaração do LLM isolada não é prova.

**Riscos/testes:** manter esclarecimento para ambiguidade e aceitar definição explícita de gasto como fatura; distinguir despesas operacionais ausentes da Gold; testar receitas, faturamento, valores com/sem tributos e definições fornecidas pelo usuário versus pelo assistente.

## 4. Caetés: município e bairros

**Evidência disponível:** a consulta auditada filtrou municipio por Caetés e retornou COUNT igual a zero. A resposta registrada informou ausência de registros, sem mencionar bairros nem Abreu e Lima. A Gold atual não contém município correspondente no cadastro, mas contém Caetés I, II e III em Abreu e Lima. Não foi encontrado o episódio numérico sobre bairros descrito no relato.

**Classificação:** não é possível atribuir ao registro disponível a troca de município por bairro ou alucinação numérica. COUNT zero gera uma linha válida e pode resultar em ANSWERED; isso não prova que a localidade foi corretamente resolvida. Ausência de município no cadastro não significa inexistência da cidade no mundo real.

**Menor correção candidata:** resolver nível geográfico e correspondência em catálogo da Gold; diante de município não coberto e bairros homônimos, pedir confirmação, sem promover bairros a município ou expandir prefixos automaticamente. Isso pode ser determinístico, sem novo LLM.

**Riscos/testes:** homônimos em municípios diferentes, nomes com acento, prefixos, municípios fora da cobertura e UC distinta versus quantidade de eventos. O episódio relatado precisa de correlação adicional para verificar seus números; não inventar um diagnóstico histórico.

## 5. DEC móvel com referência em junho de 2026

**Evidência:** a consulta aprovada usa dec_12m_horas, não apenas dec_horas, com referência 2026-06. O dicionário e o notebook definem soma dos 12 indicadores mensais, incluindo o mês de referência. A comparação na Gold encontrou 12 meses por alimentador; a maior diferença entre o campo móvel e a soma dos valores mensais publicados foi 0,0003, compatível com o arredondamento de cada campo a quatro casas. O notebook soma antes do arredondamento final. A reexecução do ranking retornou dez linhas e passou na validação numérica.

**Classificação:** não há evidência de erro de janela nesse SQL. Filtrar junho seleciona a posição do acumulado de julho de 2025 a junho de 2026. Não corrigir esse filtro para somar janelas móveis sobrepostas.

**Menor ação:** manter a receita correta e explicitar período/referência na resposta. Para seis meses, usar o acumulado dos indicadores mensais conforme o contrato; a razão dos totais entre meses é média mensal ponderada, não o acumulado do período.

**Riscos/testes:** janela inclusiva, dados incompletos, denominadores variáveis, agregação entre alimentadores, arredondamento e ausência de soma de janelas sobrepostas. O teste sintético distingue 12 meses, seis meses e somente o mês de referência.

## 6. Ranking municipal de consumo com emoji

**Evidência:** o registro com emoji terminou EXECUTION_ERROR, sem provider_error; sua mensagem corresponde a TIMEOUT. A C4.3 reexecutada com o limite existente de 10 s retornou timeout em 10,158 s. O plano percorre fato_consumo_faturamento e usa ordenação temporária; não há filtro temporal na consulta. O input guardrail aceita a pergunta com e sem emoji. Outro pedido anterior desse tema terminou INSUFFICIENT_CONTEXT na C4.1, o que é uma falha distinta.

**Classificação:** custo de execução SQL no registro do emoji, sem evidência de que o emoji causou o timeout.

**Menor correção candidata:** considerar fato_segmento_mensal, agregado que já existe na Gold e tem contrato de somas aditivas de consumo por mês/município/bairro/classe, mas não está descrito no contexto atual do agente. Uma consulta candidata sobre esse agregado retornou três linhas em 0,237 s. É uma medição isolada e ainda não foi feita reconciliação integral dos resultados dessa consulta com a consulta lenta; esta excedeu o limite. O contrato documenta reconciliação na construção da Gold.

**Riscos/testes:** demonstrar equivalência do período, filtros, grão e população antes de expor o agregado à geração; não usar agregados para filtros ausentes nem somar contagens de UCs ao longo dos meses. Verificar o plano e executar benchmarks repetidos. Não aumentar timeout como correção automática.

## Lacuna transversal da C5

Na auditoria inicial, os testes reproduziram quatro expectativas não atendidas: número existente associado a métrica errada, unidade errada, município errado ou período trocado. Esses quatro casos inicialmente usavam xfail(strict=True). Após as correções abaixo, passaram a exigir bloqueio efetivo; as expectativas foram preservadas. Números sem qualquer sustentação continuam bloqueados.

A síntese recebe pergunta, SQL e resultado, mas não recebe diretamente a memória conversacional. Assim, interpretação errada incorporada ao SQL pode gerar texto numericamente fundamentado sobre o filtro errado. Consistência numérica não equivale a consistência semântica.

## Plano recomendado para revisão

1. Preservar a última intenção válida e distinguir esclarecimentos de fatos/decisões confirmadas. Tratar follow-ups como alterações parciais, sem novo LLM e sem alterar C2/Redis nesta etapa.
2. Tornar explícitas as decisões financeira e geográfica, confrontadas com o contrato Gold e a consulta. A intenção resolvida precisa de evidência verificável, não apenas de um booleano emitido pelo modelo.
3. Vincular afirmações da síntese a métrica, unidade, localidade, período e linha de resultado. Começar por validações estruturadas verificáveis; manter os guardrails atuais. Evitar um segundo LLM como remendo padrão.
4. Habilitar o agregado de consumo já existente somente após reconciliação de resultados e testes de cobertura. Manter os limites atuais durante a avaliação.
5. Reexecutar uma matriz conversacional em ambiente isolado com providers configurados, medir aprovação, esclarecimentos necessários/desnecessários, latência e regressões. Nenhuma medição sintética garante comportamento do LLM real.

## Artefatos

O diagnóstico acima descreve a investigação inicial. A implementação autorizada posteriormente está documentada a seguir. Sem commit, push ou alteração do PR.


## Correções implementadas e limites — 04/11/2026

- Memória: respostas longas são abreviadas no contexto, preservando a pergunta; outcomes não respondidos são identificados. O armazenamento e o TTL permanecem intactos.
- Continuidade: alterações explícitas de período e DEC/FEC são aplicadas à pergunta anterior, preservando os demais termos. Na ausência de uma referência compatível, exige esclarecimento. A resolução é conservadora: não constitui um interpretador universal de linguagem natural.
- Ambiguidade financeira: gastos/despesas exigem esclarecimento, salvo definição explícita do próprio usuário; uma afirmação anterior do assistente não serve como definição.
- Geografia: consulta somente leitura ao catálogo da Gold identifica correspondências ambíguas entre município e bairro e pede esclarecimento. A extração de localidades tem cobertura limitada; falhas de acesso ao catálogo preservam o fluxo normal, sem presumir correspondência.
- C5: bloqueia afirmações explícitas incompatíveis com a família de métrica, unidade, município ou associação mês/valor verificável nas linhas retornadas. Mantém a regeneração existente. Não comprova toda a semântica do SQL nem interpreta toda forma de prosa; aliases e afirmações implícitas continuam sendo limitações.
- Consumo: a reconciliação somente leitura da Gold comparou 53.088 grupos por mês/município/bairro/classe, sem diferenças nos valores agregados. O processamento dessa comparação levou 22,811 s. O agregado existente foi incluído no contrato do agente. Uma transformação AST restrita substitui SUM(consumo_kwh) sobre a tabela detalhada somente para consultas simples com dimensões cobertas; consultas incompatíveis permanecem intactas. Não altera a Gold, limites de execução ou contagens de UCs.
- Cache: nenhuma chave, regra de TTL ou implementação Redis foi alterada. As verificações de ambiguidade antecedem a entrega de respostas em cache para impedir a reutilização de interpretações ambíguas antigas. Isso pode exigir esclarecimento onde antes havia uma resposta armazenada.

### Validação e riscos remanescentes

Testes cobrem deltas de período e métrica, definição financeira pelo usuário, catálogo geográfico, bloqueios semânticos e equivalência da transformação SQL. O fluxo HTTP DEC 12 meses → DEC 6 meses → FEC 6 meses usa SQLite e auditoria reais em arquivos temporários, com providers simulados; não é comprovação de qualidade dos modelos remotos. A medição anterior de 0,237 s para o agregado é isolada, não uma promessa de latência.

Permanecem pendentes a avaliação repetida com providers reais e a validação semântica completa entre intenção e SQL. As proteções implementadas reduzem classes verificáveis de erro, mas não garantem ausência de interpretações incorretas. Não houve alteração da ordem dos modelos, timeouts, fallback, frontend, dados Gold ou instrumentação Logfire. Containers não foram reconstruídos nesta validação.


### Resultado final da validação local

- Backend completo: 1.912 aprovados, 19 ignorados (integrações externas opcionais), sem falhas.
- Frontend: 81 aprovados; build TypeScript/Vite concluído.
- `git diff --check`: sem erros.
- Não foi executada uma nova conversa com providers remotos nesta conclusão. A listagem Docker não apresentou containers em execução; nenhum container foi iniciado ou reconstruído.
- O fixture textual do contrato Gold foi sincronizado com o contexto de produção, mantendo o teste de igualdade. Os testes de bloqueio semântico mantêm a expectativa de rejeição; não foram removidos para obter aprovação.


## Regressões manuais — investigação e correções adicionais

A inspeção do container em execução confirmou `ModuleNotFoundError: app.agent.conversation`: a imagem servindo o site não continha as correções locais. Isso explica a divergência entre o esclarecimento financeiro determinístico local e respostas reais sobre receita. Não se deve interpretar testes locais como evidência de implantação.

A auditoria SQLite, lida em modo somente leitura e sem imprimir conteúdo, confirmou uma alteração para seis meses com OUTPUT_BLOCKED, uma regeneração e dez linhas; o SQL ainda referenciava indicador móvel de 12 meses. A consulta FEC seguinte terminou ANSWERED e também usou 12 meses. A política anterior excluía OUTPUT_BLOCKED da memória. As respostas intermediárias rejeitadas e o motivo detalhado da C5 não são persistidos nessa auditoria: não é possível atribuir categoricamente a inconsistência numérica a uma frase ou arredondamento específico.

Correções adicionais:

- Uma tentativa bloqueada preserva somente a pergunta do usuário e um marcador fixo de intenção pendente, nunca a resposta rejeitada. O outcome continua identificado como bloqueado e não elegível ao cache.
- A síntese e sua validação recebem a pergunta resolvida com o contexto, assim como a geração SQL.
- Uma janela explícita diferente de 12 meses não pode executar SQL usando dec_12m_horas/fec_12m. Na incompatibilidade detectada, a execução é interrompida com esclarecimento, sem enfraquecer a C5 ou inventar outro SQL.
- Pedidos referenciais explícitos de gráfico resolvem a intenção anterior apenas quando o último turno foi aprovado. Sem referente aprovado, pedem esclarecimento. O pipeline existente consulta dados e aplica C5/C6 normalmente; não reconstrói séries a partir da prosa.
- Localidade ausente do catálogo disponível exige confirmação e informa que ausência de cobertura não comprova zero. Município coberto segue o fluxo SQL normal, onde uma contagem zero pode ser comprovada.

Limites: a memória atual não contém o conjunto de linhas/visualização aprovado. Portanto, o pedido de gráfico pode executar novamente SQL e síntese; reutilização direta sem nova execução exige ampliar o contrato de memória com uma referência verificável ao resultado aprovado. Essa ampliação não foi feita. A extração de localidades e a resolução de deltas continuam conservadoras. A rejeição de janela incompatível evita resposta incorreta, mas pode reduzir a taxa de respostas até o modelo gerar a janela correta. Não foram reiniciados containers nem consumidas cotas de providers remotos nesta rodada; a imagem atual deve ser reconstruída antes dos próximos testes manuais.


Complemento de visualização: o contrato interno de memória passou a aceitar opcionalmente a visualização já aprovada pela C6 e sua versão Gold. O pedido referencial só entrega esse objeto quando o último turno está aprovado, pertence à sessão recuperada e tem a mesma versão Gold. Sem essa evidência (inclusive memórias antigas), solicita nova consulta em vez de chamar LLM ou fabricar dados. Nenhuma linha bruta é adicionada à memória ou telemetria. Os campos novos são opcionais para compatibilidade com entradas antigas. A descrição anterior de reexecução se refere ao caminho intermediário, substituído por essa recuperação explícita.


Validação final desta rodada: backend completo com 1.924 testes aprovados e 19 integrações opcionais ignoradas; frontend com 81 testes aprovados; git diff --check sem erros. A matriz HTTP inclui a segunda resposta bloqueada e a troca posterior para FEC mantendo seis meses. A recuperação de gráfico tem testes positivos e negativos por sessão, versão, outcome e presença de visualização. Não há comprovação de recuperação de qualidade com providers reais nesta rodada, nem de atualização da imagem em execução. A C5 mantém as regras e a regeneração existentes. Redis/C2 mantêm chaves, TTL e regras de HIT/MISS; apenas o contrato opcional da memória C7 foi ampliado. Entradas antigas sem visualização geram esclarecimento nesse novo caminho.


## Revisão final: TOP, esclarecimento financeiro e recorte geográfico

### Evidências reais

- Dois pedidos TOP 15 na auditoria terminaram NEEDS_CLARIFICATION sem SQL e com mensagem de localidade. Ambos continham a construção “em ordem”. O extrator interpretava qualquer expressão após “em” como localidade inexistente. A ausência de correspondência só bloqueia agora um nome próprio candidato ou um nível geográfico explícito; expressões comuns não viram filtros geográficos.
- A confirmação de despesas operacionais encontrava novamente a função de ambiguidade, que só reconhecia definições de faturamento. Agora despesas operacionais explícitas terminam INSUFFICIENT_CONTEXT antes de SQL/LLM, pois essa métrica não existe no contrato.
- A auditoria confirmou duas respostas sobre bairros com SQL de consumo, três linhas e referência a novembro de 2025. O resolvedor anterior só entendia deltas temporais e DEC/FEC; não resolvia mudanças geográficas. Além disso, INSUFFICIENT_CONTEXT não preservava o pedido inicial na memória, permitindo perder o referente. Agora esse outcome preserva apenas a pergunta e um marcador fixo, sem conteúdo não aprovado. Deltas geográficos delimitados substituem a localidade e conservam a métrica/período originais, inclusive após esclarecimento ou indisponibilidade. Não é possível reconstruir referências antigas já descartadas.
- As consultas financeiras auditadas usam kpis_mensal, uma com receita_energia e outra com receita_total. Consulta somente leitura à Gold confirmou em 2025-11: receita_energia = R$ 13.361.910,75; receita_total = R$ 17.815.881,15. A diferença é de definição (sem/com tributos), não evidência de números inventados. “Valor faturado” usa total com tributos; pedidos explícitos de receita de energia usam a métrica sem tributos.

### Proteções e limites

O novo validador estrutural de intenção rejeita limites explícitos divergentes do TOP, troca comprovada entre métricas financeiras e consumo em consulta sobre UCs afetadas por interrupções. É usado na geração e na C5; bloqueios não são convertidos em aprovação. Uma janela de “últimos 12 meses” não é interpretada como TOP 12. Prompts foram alinhados ao contrato. C2, chaves/TTL Redis, providers e Gold permanecem intactos.

As verificações são conservadoras e cobrem contradições demonstráveis, não toda a semântica de qualquer SQL. SQL incompatível pode terminar em esclarecimento em vez de uma resposta; não há nova chamada ao modelo para corrigir silenciosamente. Deltas de localidade só são resolvidos quando há um recorte anterior delimitado; formas não reconhecidas continuam sujeitas à interpretação do modelo. A elegibilidade de memória para INSUFFICIENT_CONTEXT foi atualizada explicitamente nos testes; respostas não aprovadas são substituídas por marcador fixo.

Testes adicionais: preposição não geográfica; município realmente desconhecido; mudança de município para bairros após indisponibilidade, seguida de restrição a um bairro; TOP 15 versus LIMIT 10/15; janela temporal versus quantidade; métricas financeiras positivas e negativas; C5 bloqueando número existente da métrica errada; fluxo HTTP de esclarecimento financeiro sem SQL/LLM. A suíte integral inclui as regressões existentes de HIT/MISS, visualização, auditoria e privacidade.


Resultado desta revisão: 1.939 testes backend aprovados, 19 integrações externas opcionais ignoradas; 81 testes frontend aprovados e build concluído; git diff --check sem erros. Backend Docker reconstruído com o código atual, frontend reiniciado para atualizar a rota do proxy, Redis mantido sem reinício ou limpeza. Health HTTP 200 e fluxo real pelo proxy “gastos → despesas operacionais” confirmado: esclarecimento no primeiro pedido e indisponibilidade no segundo, sem chamadas ao provider. As demais regressões usam providers simulados; não houve nova medição de qualidade dos providers remotos. Sem commit, push ou alteração do PR.


## Sequência real: UCs interrompidas e correção para bairros

A auditoria das duas últimas interações confirmou mesma sessão, cache_hit=0 em ambas, primeiro COUNT(DISTINCT id_uc) em fato_interrupcao retornando uma linha e depois SELECT detalhado em fato_consumo_faturamento retornando 500 linhas com truncated=1. A leitura direta da lista de memória Redis (sem atualizar TTL e sem imprimir identificadores/chaves/conteúdo) confirmou as duas perguntas presentes. Não foi perda física da memória nem HIT responsável por essas respostas.

Causas: (1) cobertura buscava somente “em”, deixando escapar “no município”; (2) delta geográfico não reconhecia o prefixo de correção “na verdade, quero” nem a retomada “no mesmo período”; (3) a verificação semântica exigia a justaposição “UCs afetadas”, não reconhecendo “UCs foram afetadas”, e só detectava consumo em nomes de colunas. Com a pergunta incompleta na geração e síntese, a C5 numérica conseguia validar números de uma fonte errada.

Correções: extrair primeiro município explicitamente nomeado, resolver prefixos de correção e manutenção de período antes do processamento, e exigir estruturalmente COUNT(DISTINCT id_uc) na fonte fato_interrupcao para pedidos de quantidade de unidades afetadas. Listagens de faturas, COUNT(*), COUNT(id_uc), fonte não correspondente, agrupamento por unidade e planos complexos sem prova são rejeitados. Validação compartilhada pela geração e C5, sem relaxar bloqueios ou mudar providers/C2/Redis/Gold. Formas complexas legítimas podem gerar esclarecimento conservador.

SQLs sanitizados da auditoria:

```sql
-- Primeiro pedido: SQL correto quanto à operação, mas sem cobertura comprovada.
SELECT COUNT(DISTINCT id_uc) AS ucs_afetadas
FROM fato_interrupcao
WHERE municipio = :municipio AND mes_referencia >= :inicio AND mes_referencia <= :fim;
-- Segundo pedido incorreto: detalhamento de faturas, agora rejeitado.
SELECT id_uc, mes_referencia, consumo_kwh, valor_total
FROM fato_consumo_faturamento
WHERE municipio = :municipio AND bairro IN (:b1,:b2,:b3)
  AND mes_referencia >= :inicio AND mes_referencia <= :fim;
-- Operação correta para o segundo pedido:
SELECT COUNT(DISTINCT id_uc) AS ucs_afetadas
FROM fato_interrupcao
WHERE municipio = :municipio AND bairro IN (:b1,:b2,:b3)
  AND mes_referencia BETWEEN :inicio AND :fim;
```

A consulta corrigida foi executada somente em leitura na Gold: 139 UCs distintas afetadas. Cadastro do recorte: 293 UCs; município do primeiro pedido: nenhuma correspondência cadastral. Não inferir zero interrupções a partir dessa ausência. Os valores são evidência deste snapshot e recorte, não constantes introduzidas no código.

Validação: 48 testes focados antes da proteção adicional de agrupamento, depois 11 testes do novo arquivo; suíte completa final com 1.950 aprovados e 19 integrações opcionais ignoradas. HTTP sintético usa SQL/C4.2/C5/C7 reais em SQLite temporário e providers simulados. Casos negativos verificam rejeição antes de execução e na C5. Backend Docker reconstruído, Redis preservado e sem limpeza global. SQL de contagem corrigida não retorna listagem de UCs.


Validação final com providers reais no Docker atualizado: primeira pergunta HTTP 200/NEEDS_CLARIFICATION em 0,88 s, sem SQL; segundo pedido HTTP 200/ANSWERED em 11,4 s, com resposta contendo 139 e sem SQL de consumo. Auditoria confirmou cache_hit=0 em ambos; segunda consulta COUNT(DISTINCT id_uc) em fato_interrupcao, uma linha agregada, truncated=0 e regenerations=0. Esse tempo é uma execução isolada, não garantia de latência. git diff --check sem erros. Sem commit ou push.


## Gráfico e consumo anual municipal — correção validada

O ranking DEC auditado tinha três colunas e indicador dec_12m_horas com referência 2026-06. A C6 descartava todos os resultados que não tivessem exatamente duas colunas. O follow-up “exibe um grafico disso” não era reconhecido pela gramática, sendo entregue à C4.1 e classificado fora do escopo. Agora flexões imperativas comuns são reconhecidas; a C6 aceita duas dimensões textuais conhecidas e uma única medida numérica, com rótulos compostos únicos. Não soma linhas, não inventa categorias e não modifica o resultado original. Dados truncados, medidas múltiplas ou identidades ambíguas continuam sem gráfico. A memória recebe também a visualização de respostas cacheadas aprovadas, mantendo a recuperação posterior; o HIT não regrava cache nem renova TTL.

O caso Recife/2025 não tinha registro anterior localizável na auditoria. Foi reproduzido com provider real: HTTP 200/EXECUTION_ERROR em 11,67 s, sem provider_error, SQL SUM(consumo_kwh) na tabela detalhada com filtro ano=2025. Não é evidência de indisponibilidade do modelo, e sim timeout da C4.3. Uma segunda execução usou SUBSTR(mes_referencia,1,4), forma também não coberta pela otimização, e falhou em 13,32 s. Esses dois filtros anuais agora são normalizados de forma restrita para intervalo mensal e elegibilidade do agregado. Não foram alterados modelos, timeouts ou fallback.

Comprovação somente leitura na Gold: nenhuma divergência entre ano e ano da competência na tabela detalhada; consumo municipal por ano e por intervalo mensal iguais a 86.921.361 kWh. Reconciliação completa levou 45,265 s; consulta ao agregado retornou o mesmo valor em 0,529 s. Medições isoladas, não SLA nem benchmark controlado. Filtros por UC/GD/medidor ou operações não aditivas não são reescritos.

Validação final com provider real: consumo municipal respondeu 86.921.361 kWh em 4,07 s; auditoria confirma ANSWERED, cache_hit=0, uma linha e fonte fato_segmento_mensal. Ranking DEC respondeu com gráfico em 3,42 s; o follow-up imperativo recuperou o gráfico em 0,02 s sem chamada ao modelo. Há teste para gráfico após HIT sem regravação de cache. A síntese foi orientada a distinguir acumulado e mês de referência.

Suíte completa: 1.973 aprovados, 19 integrações opcionais ignoradas. Frontend: 81 aprovados e build concluído. git diff --check sem erros. Docker atualizado; Redis mantido sem limpeza/recriação. Dados Gold inalterados. Sem commit ou push.

Limites: resultados antigos cacheados sem visualização não podem ter seus dados reconstruídos a partir da prosa; é necessário consultar novamente quando não há objeto aprovado. Outras formas de SQL não comprovadamente equivalentes continuam no caminho original e podem atingir os limites existentes. Novas medições com providers podem variar; nenhuma redução universal de latência foi demonstrada.


## Bloqueio do ranking DEC acumulado após teste manual

Auditoria do episódio: OUTPUT_BLOCKED, dez linhas, cache_hit=0, provider_error ausente e uma regeneração. O SQL executado soma dec_12m_horas por alimentador em uma única competência. As respostas rejeitadas/motivo exato não foram persistidos historicamente. Em reprodução sobre o mesmo SQL e dados, a C5 rejeitou ambas as sínteses por UNSUPPORTED_NUMBER. Uma reprodução adicional isolou exclusivamente o numeral “12” em “12 meses”: o nome da coluna móvel contém a evidência semântica do período, mas o extrator numérico não a considera literal SQL.

Correção restrita: reconhecer o período “12 meses” somente quando uma projeção direta ou SUM de dec_12m_horas/fec_12m da tabela contratada corresponde à coluna do resultado. A exceção não adiciona 12 ao conjunto geral de medidas válidas; “12 horas”, outro período, SQL mensal ou valor declarado apenas pelo usuário permanecem bloqueados. Sem mudança de providers, tentativas ou regras de cache. Testes positivos e negativos cobrem os dois indicadores.

Validação real da pergunta exata após reconstruir Docker: HTTP 200/status ok, com gráfico, em 4,78 s. A variabilidade das respostas do modelo continua existindo; esta evidência valida essa reprodução e não identifica com certeza o texto rejeitado no episódio histórico. Sem commit/push.
