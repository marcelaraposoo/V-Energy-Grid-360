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
Não inferimos independência semântica: contexto alterado implica MISS hoje.

A C1 normaliza texto e valida segurança; não resolve intenção. A C4.1 interpreta
a pergunta usando memória depois da C2. Não há evidência estruturada antes do
GET para separar pergunta independente de acompanhamento. "E no mês anterior?"
não pode reutilizar uma resposta antiga apenas porque o texto é igual. Perguntas
com redações diferentes também dão MISS. Isso preserva confiabilidade, mas ainda
não entrega cache independente da memória para perguntas livres.

## Identidade e isolamento

`agent:answer:v3:<scope_sha256>:<query_sha256>`

O scope identifica sessão e identidade de usuário, quando disponível. A identidade
da consulta inclui pergunta normalizada pela C1, sessão, usuário, versão Gold e
contexto efetivo. Valores não aparecem em texto puro nas chaves. A função de
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
recrie o backend para adotar a política. Não foram editadas credenciais locais.

## C7 e cache HIT

HIT evita SQL/providers e preserva texto, assumptions e gráfico integralmente.
Continua gerando request_id novo e auditoria C7 com `cache_hit=true`, sem SET.
Na memória, a entrega não duplica um turno consecutivo idêntico. Se outra
pergunta estava por último, o turno da entrega atual precisa ser registrado para
que o próximo acompanhamento aponte ao referente correto. O adapter Redis
compara/anexa/limita/renova TTL atomicamente, inclusive sob concorrência. A C7
mantém elegibilidade dos outcomes e falhas best-effort. Logfire continua exportando
somente sua whitelist; conteúdo e histórico não entram na telemetria.

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
continua no pipeline atual. Essa evolução não foi implementada nesta tarefa:
falta um resolvedor confiável no contrato atual; fingir equivalência seria inseguro.

## Validação

A suíte cobre identidade, sessões/usuários no construtor de chaves, versões,
contexto, recuperação após outra pergunta com snapshot idêntico, MISS para
paráfrases e métricas distintas, TTL, payload completo, auditoria e concorrência.
`backend/tests/manual/validate_cache_session_limits.py` usa Redis real com chaves
sintéticas isoladas e removidas ao final; testa limite concorrente, isolamento,
expiração, GET sem renovar TTL, deduplicação de memória e sequência A→B→A.
Os testes não comprovam equivalência semântica para linguagem natural livre.
