# C2 — cache automático e memória conversacional

## Implementado e limites atuais

C2 armazena `PostProcessingResult` aprovado: texto, assumptions e visualização.
C7 mantém memória para compreender o diálogo. O botão de repetir consulta e o
parâmetro `repetir_ultima` foram removidos; não existe recuperação por tema.
Nenhuma chamada LLM adicional foi introduzida.

O cache conserva respostas anteriores até sua expiração ou remoção pelo limite
por sessão. Não é limitado à última resposta. Recupera automaticamente uma
pergunta normalizada quando o contexto efetivo também for idêntico, inclusive
após outros pedidos se esse contexto permanecer ou voltar a ser idêntico.
O caminho contextual mantém esse critério. Antes do SQL, recuperação independente
exige o certificado determinístico descrito abaixo. Quando ele não existe, há uma
segunda oportunidade de recuperação depois da geração e validação do SQL.

A C1 normaliza texto e valida segurança; não resolve intenção. A C4.1 interpreta
a pergunta usando memória depois da C2. Para texto livre geral não há evidência estruturada antes do GET. O contrato
limitado de ranking global completo descrito abaixo é a exceção verificável. "E no mês anterior?"
não pode reutilizar uma resposta antiga apenas porque o texto é igual. O segundo
lookup compara também o SQL resolvido no contexto atual. Perguntas com redações
diferentes continuam dando MISS: não há equivalência semântica artificial.

## Identidade e isolamento

`agent:answer:v3:<scope_sha256>:<query_sha256>`

O scope identifica sessão e identidade de usuário, quando disponível. A identidade
da consulta inclui pergunta normalizada pela C1, sessão, usuário, versão Gold e
contexto efetivo e versão da política de cache. A política
`approved-deterministic-v1` invalida logicamente entradas anteriores, sem DELETE.
Valores não aparecem em texto puro nas chaves. A função de
chave aceita `user_identity` interno, mas o HTTP atual não oferece autenticação
nem identidade confiável: não declaramos isolamento por usuário autenticado em
produção. O backend não aceita identidade de usuário via body para autorizar
cache. Ownership/autorização de sessão permanece pendente com DEV, conforme C7.
Sem sessão não vazia, a C2 não faz GET/SET; uma UUID no navegador não é prova de
ownership nem garantia de sessão válida no backend.

Nova conversa gera outra sessão. Outra versão Gold produz outra chave: invalidação
lógica sem limpar o Redis inteiro. O namespace v3 não lê entradas v2. Falta de
memória por erro/corrupção continua impedindo GET/SET. TTL não substitui identidade.

## Expiração e limites

| Configuração | Padrão | Comportamento |
|---|---|---|
| `CACHE_TTL_SECONDS` | 86400 | 24 h por resposta, contadas do SET; GET não renova |
| `CACHE_MAX_ENTRIES_PER_SESSION` | 100 | Todas as perguntas/contextos/versões no mesmo scope |
| `CACHE_TIMEOUT_SECONDS` | 1 | Limite de operação Redis |
| `MEMORY_TTL_SECONDS` | 86400 | Renovado ao ler memória válida ou finalizar turno elegível |
| Limite de memória | 20 turnos | Contexto usa até 5 e 4000 caracteres |

Um índice técnico sorted set por scope permite limitar armazenamento de forma
atômica: SET com TTL, remoção de referências expiradas e evicção das entradas
mais antigas acima do limite ocorrem num script Redis. O índice tem expiração
compatível com as entradas; não contém outra cópia de perguntas/respostas. O GET
continua revalidando o payload via Pydantic estrito e respeitando a expiração do
Redis. Duas escritas concorrentes não ultrapassam o limite após a operação.

O Redis atual do Compose é volátil (tmpfs, sem persistência). Reiniciá-lo invalida
memória/cache mesmo com navegador aberto. Fechar o navegador não apaga o Redis;
o TTL e os limites são a garantia no backend. Aumentar o TTL no código não muda
entradas existentes nem overrides de 300 s em `.env`/terminal. Configure 86400 e
recrie o backend para adotar a política. Nesta correção, o override local de
`CACHE_TTL_SECONDS=300` foi ajustado para 86400 e o backend foi recriado. As
credenciais e os parâmetros dos providers foram preservados. Entradas antigas
não recebem prazo adicional.

## C7 e cache HIT

O HIT antes de C4.1 evita SQL e providers. O HIT após C4.2 ainda usa a geração
SQL, mas evita C4.3, C4.4, C5 e C6, recuperando somente um payload anteriormente
aprovado. Ambos preservam texto, assumptions e gráfico integralmente. Continuam
gerando request_id novo e auditoria C7 com `cache_hit=true`, sem SET. No segundo
caminho, as tentativas reais de geração continuam contadas; a auditoria não marca
um SQL como executado quando houve apenas geração e recuperação.
Na memória, a entrega não duplica um turno consecutivo idêntico. Se outra
pergunta estava por último, o turno da entrega atual precisa ser registrado para
que o próximo acompanhamento aponte ao referente correto. O adapter Redis
compara/anexa/limita/renova TTL atomicamente, inclusive sob concorrência. A C7
mantém elegibilidade dos outcomes e falhas best-effort. Logfire continua exportando
somente sua whitelist; conteúdo e histórico não entram na telemetria.

## Recuperação geral após SQL validado

`state/sql_cache.py` implementa `validated-sql-plan-v2`. Depois de C4.1 e do ALLOW
da C4.2, antes de executar C4.3, há outro span C2. A identidade inclui a mesma
pergunta normalizada, sessão, versão Gold e hash de toda a AST SQL canônica.
A memória continua sendo usada normalmente para gerar a consulta atual, mas seu
hash integral deixa de impedir a recuperação quando o SQL resolvido é igual.

A canonicalização remove diferenças de formatação/capitalização dos
identificadores. Também elimina aliases de saída locais quando é possível
resolver exatamente seus bindings no ORDER BY: a expressão subjacente e a
ordenação efetiva precisam ser iguais. Aliases duplicados, referenciados fora
do ORDER BY, conflitantes ou usados em subqueries do ORDER BY não são
reinterpretados. O payload já aprovado é autocontido e preserva os rótulos
originais. Preserva métrica, expressões projetadas, tabelas, filtros/literais,
período, agrupamento, ordenação e limite. SQL diferente dá MISS; não convertemos
soma de DEC mensal em DEC móvel, nem gastos em receita. Ainda pode haver MISS
quando duas gerações escolhem receitas SQL diferentes para a mesma pergunta.
Cada forma aprovada pode aquecer uma entrada própria, dentro do limite da sessão.

O período relativo precisa estar resolvido no SQL em relação ao snapshot Gold
versionado. Por exemplo, datas absolutas diferentes produzem identidades
diferentes. Referente diferente que produza outro filtro também dá MISS.
O cache não prova que a interpretação do modelo está correta; mantém as mesmas
validações funcionais existentes. Não acrescenta resolvedor semântico por texto.

Somente SELECT de uma instrução, sem comentários, parâmetros pendentes ou funções
fora da lista determinística são elegíveis. Relógio corrente, aleatoriedade e
funções desconhecidas não são cacheados, nem pelo caminho contextual. A resposta
normal continua possível. LIMIT sem ORDER BY também não recebe essa identidade.
A lista é conservadora; ampliar funções exige prova de determinismo e testes.

Na C7, resposta completa, não truncada e aprovada publica payload e ponteiro para
o plano no mesmo script Redis já usado para capacidade/TTL. Não duplica payload,
SQL ou memória. Ponteiro e alvo têm a mesma expiração; leitura atômica exige TTL
positivo, mesmo scope, contrato/hash exatos e payload Pydantic estrito. HIT não
renova prazo. Evicção remove o ponteiro se ainda apontar para o alvo removido,
preservando publicações concorrentes mais recentes.

Logfire recebe somente `cache_phase` (`pre_sql`/`post_sql`) e `cache_reason` de
uma enumeração fechada: hit, not_found_or_expired, payload_invalid, redis_error,
plan_mismatch, unsupported_plan, cache_disabled, session_missing ou
memory_unavailable. Ausência e expiração não são distinguidas sem evidência.
Perguntas, respostas, SQL, chaves, hashes e sessão não são exportados. Falhas de
Redis, payload ou lookup viram MISS; falha de telemetria não quebra a aplicação.

## Evolução proposta: intenção resolvida antes da C2

Para separar definitivamente cache e memória, a menor evolução de contrato é
um `ResolvedQueryIntent` validado antes do lookup, contendo:

- métrica e perspectiva financeira explícitas (receita, valor faturado e despesa são distintas);
- operação, filtros tipados e valores, período absoluto e calendário;
- granularidade, ordenação, quantidade/top-N e escopo do subconjunto;
- versão do contrato/Gold e identidade autenticada/sessão;
- resolução das referências ou marcação explícita de que ainda faltam dados.

Nível A: texto normalizado pode apontar à intenção somente se a resolução atual
for comprovadamente a mesma. Intenção independente e completamente resolvida não
inclui o hash da conversa inteira. Acompanhamento precisa resolver novamente seu
referente em atributos absolutos; referente diferente implica outra identidade.

Nível B: intenções canônicas iguais podem compartilhar resposta dentro do mesmo
scope, mesmo com textos diferentes. Sem intenção completa, MISS. Não usar apenas
palavras parecidas, embeddings, aliases de SQL ou declaração não verificada do
modelo como certificado. Um campo emitido pela C4.1 existente não basta para
interpretar a próxima pergunta antes da C2.

Uma entrada estruturada de consulta (ou parser determinístico com gramática
explicitamente suportada e validação de todos os atributos) é o caminho menor
para produzir esse contrato sem novo LLM. Texto livre fora dessa cobertura
continua no pipeline atual. Essa evolução geral ainda não foi implementada: falta um resolvedor confiável
para linguagem natural livre. A implementação limitada abaixo não substitui esse resolvedor.

## Validação

A suíte cobre identidade, sessões/usuários no construtor de chaves, versões,
contexto, recuperação após outra pergunta com snapshot idêntico, MISS para
paráfrases e métricas distintas, TTL, payload completo, auditoria e concorrência.
`backend/tests/manual/validate_cache_session_limits.py` usa Redis real com chaves
sintéticas isoladas e removidas ao final; testa limite concorrente, isolamento,
expiração, GET sem renovar TTL, deduplicação de memória e sequência A→B→A.
Os testes não comprovam equivalência semântica para linguagem natural livre.


## Ciclo de vida da sessão na interface

A instância de sessão é criada uma vez pelo inicializador lazy do estado React de
`AssistentePage`. Todos os pedidos dessa conversa capturam o mesmo ID. Nova
conversa troca o ID e limpa o histórico visual juntos, sem DELETE ou limpeza
Redis. F5/Ctrl+R, remount da página, outra aba e reabertura do navegador criam
instâncias novas, com histórico vazio e IDs novos. Não se usa localStorage,
sessionStorage, cookie ou parâmetro de URL para restaurar a conversa.

Respostas pendentes só são exibidas se o componente estiver montado e o ID
capturado ainda pertencer à conversa atual. Uma resposta antiga não altera o
loading de outra sessão. Dados anteriores continuam isolados e sujeitos ao TTL;
nenhuma dessas ações faz FLUSHDB, FLUSHALL ou limpeza global. Uma requisição já
aceita pelo backend pode terminar e auditar apenas sua sessão antiga.

Persistir conversas entre recarregamentos é evolução futura: será necessário
restaurar juntos ID, histórico visual e validade/ownership da sessão no servidor.
Restaurar somente o ID com interface vazia não será uma implementação válida.


## Elegibilidade registrada na primeira resposta aprovada

`state/cache_eligibility.py` define o contrato versionado
`explicit-global-monthly-v1`. Ele reconhece uma linguagem fechada de ranking,
não um classificador geral baseado na ocorrência de palavras. Exemplo aceito:

> Quais os 3 meses com maiores valores faturados em todo o histórico da distribuidora, sem filtros adicionais?

Toda a frase precisa ser consumida. Métrica (valor faturado, receita de energia
ou consumo), quantidade de 1 a 30, direção, granularidade mensal, período de todo
o snapshot e escopo sem filtros precisam estar explícitos. Valores faturados são
vinculados à métrica documentada `receita_total`; gasto ambíguo não é aceito.

A declaração da pergunta é confrontada com toda a AST SQL da primeira execução:
projeções, métrica física, tabela, GROUP BY opcional compatível com o grão mensal,
ORDER BY e LIMIT. WHERE, JOIN, período herdado, cláusulas adicionais, quantidade
ou direção diferente, múltiplos statements e aliases livres não recebem prova.
Somente nomes neutros/documentados são permitidos em aliases. C4.2/C4.3/C5/C6
continuam obrigatórias para a resposta inicial. Não há campo booleano produzido
pelo LLM autorizando o cache nem nova chamada ao modelo.

Na C7, somente uma resposta completa, aprovada e não truncada publica o certificado.
A entrada original recebe um envelope interno com response (payload intacto),
versão do contrato, hashes da intenção e da forma SQL e identidade do lookup.
Um ponteiro por sessão/pergunta normalizada/Gold/contrato aponta à entrada original.
O payload não é duplicado. Ele continua sendo lido como PostProcessingResult;
o envelope não aparece no contrato HTTP ou na telemetria Logfire.

O SET atômico publica payload e ponteiro com a mesma expiração. O índice existente
continua contando as entradas originais; evicção limpa seu ponteiro quando ainda
aponta para aquela entrada. Sob concorrência, remover um alvo antigo não apaga o
ponteiro de um alvo novo. O GET independente lê ponteiro e alvo atomicamente,
exige TTL positivo em ambos, mesmo scope, certificado de contrato/intenção válido
e payload estritamente validado. GET/HIT não renova TTL. Falhas viram MISS.
Autenticação/ownership continua pendente; a construção da chave aceita identidade
interna de usuário futuro, sem aceitar esse valor do cliente para autorizar acesso.

A normalização e o texto da pergunta continuam compondo o lookup: esta etapa não
faz reutilização de paráfrases. Perguntas referenciais e desconhecidas continuam
contextuais antes da geração; depois da C4.2 podem usar a comparação exata de
SQL resolvido descrita acima. Perguntas sem período/escopo explícitos não são
promovidas silenciosamente à linguagem global, mesmo que o SQL pareça parecido.
Para ampliar a cobertura será preciso fornecer uma intenção resolvida completa,
com vínculo verificável ao pedido e à AST SQL. Um campo `independent=true` ou uma
intenção não verificável emitida pelo LLM não bastariam.

### Validação Redis real e limite do cenário solicitado

`backend/tests/manual/validate_independent_cache.py` executa o pipeline e C7 com
Redis real, C4.2/C5 reais e doubles declarados de geração/síntese/execução SQL.
Não consulta Gold nem providers. Com A inequívoca do exemplo e B sobre DEC,
valida A→A e A→B→A com HIT automático, contadores de geração/execução/síntese
inalterados no HIT, texto/assumptions/gráfico preservados e auditoria C7.
Também cobre referentes alterados, bloqueio C5, sessões/versões, expiração,
concorrência e evicção. Todas as chaves sintéticas são removidas ao final.

A pergunta literal "Quais os 3 meses com maiores gastos?" ficou ambígua por decisão
confirmada pelo usuário: precisa de esclarecimento. Portanto, não há prova honesta
de MISS→resposta aprovada→SET→HIT para essa pergunta literal; o ensaio verifica
NEEDS_CLARIFICATION e ausência de índice independente para ela. A correção foi
comprovada apenas para o contrato explícito suportado, não para toda pergunta livre.


### Validação do segundo lookup com Redis real

`backend/tests/manual/validate_post_sql_cache.py` executa A→B→A→B, B→B,
referentes alterados, bloqueio C5, sessões/versões distintas, expiração,
concorrência, capacidade, prazo não renovado e preservação de texto/assumptions/
gráfico e auditoria. Redis, C4.2, C5, C6 e C7 são reais; geração, síntese e executor
SQL são doubles declarados. Não é medição de latência de providers ou ingestão
real no projeto Logfire. Os testes de observabilidade verificam a whitelist e os
spans: no HIT pós-SQL há C4.1/C4.2/C2/C7, sem C4.3/C4.4/C5/C6 adicionais.

O ensaio não comprova HIT pré-SQL para B, nem que consultas semanticamente
parecidas sejam equivalentes. Uma mudança na receita SQL produz MISS seguro.


Na investigação real após a primeira implantação, a resposta B estava ANSWERED,
não truncada, com entrada Redis válida. A repetição mudou somente aliases das
projeções e seus bindings no ORDER BY; filtros, agrupamento, limite, tabelas e
expressões subjacentes eram iguais. Isso também cobre alias de agregação com
nome igual ao da coluna de entrada: o binding dentro da expressão não é o alias
de saída. Um teste SQLite verifica que os resultados e a ordenação são iguais.
A comparação literal dos aliases gerava MISS.
Esse caso motivou a canonicalização conservadora v2, com testes negativos para
aliases ambíguos e mudanças reais de métrica/ordenação. Uma repetição bloqueada
pela C5 não substitui a entrada aprovada anterior.


### Verificação pela API real após a correção

Em 03/11/2026, com providers configurados e Gold local, uma nova sessão executou
A→B→A→B. Primeiras respostas: 3,707 s e 4,988 s. A repetida teve HIT em 0,024 s,
com texto e gráfico idênticos. B repetida ainda teve MISS (4,212 s): a auditoria e
a comparação interna mostraram SQL diferente em projeções, filtros e agrupamento;
as duas respostas foram aprovadas e tinham entradas válidas. Não houve equivalência
inventada entre elas. Após aquecer essas formas, a repetição consecutiva de B teve
HIT em 1,677 s, sem SQL executado registrado na C7.

São observações pontuais locais, não um benchmark ou garantia de latência. O HIT
pós-SQL ainda depende da geração. Portanto, C2 ganhou cobertura, mas não está
universalmente resolvida para texto livre nem garante HIT em toda repetição.
