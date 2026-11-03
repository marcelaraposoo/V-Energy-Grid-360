# Dockerização — guia para desenvolvedores

## 1. Visão geral e decisões de arquitetura

A aplicação usa **três containers**: `frontend`, `backend` e `redis`, definidos
no `compose.yaml` da raiz. O navegador acessa o frontend/Nginx; chamadas a
`/api/...` seguem pelo proxy até o backend/FastAPI, que acessa dois bancos SQLite
independentes: a Gold analítica somente leitura e o portal operacional com escrita.
Redis mantém o cache opcional de respostas finais da C2 e a memória curta de
sessão da C7, acessados pela rede Docker. Auditoria C7 fica no portal.db.

Essa organização mantém interface e API na mesma origem para o navegador,
centraliza o acesso aos dados no backend e separa dados analíticos publicados
pelo time de Dados dos registros criados pela aplicação. SQLite é acessado como
arquivo pelo processo Python e não precisa de servidor próprio.

Não há container separado para SQLite ou IA. Os componentes da IA estão no
backend. A indisponibilidade do Redis não impede a inicialização ou o health
do backend: GET falha como MISS e SET falha sem descartar resposta aprovada.

## 2. Responsabilidade de cada container

| Container | Responsabilidades |
|---|---|
| `frontend` | O build em Node executa `npm ci` e compila o React com Vite. A imagem final usa Nginx para servir os arquivos estáticos, aplicar o fallback da SPA e encaminhar `/api/...` ao backend. O Node não permanece como servidor em execução. |
| `backend` | Executa FastAPI com Uvicorn na porta interna 8000, acessa a Gold, mantém o banco operacional e incorpora os componentes e prompts da IA. |
| `redis` | Cache C2 e memória curta C7 na porta interna 6379; healthcheck com `redis-cli ping`, sem porta publicada no host. |

O fallback da SPA permite abrir diretamente uma rota como `/uc`: quando não há
arquivo estático correspondente, o Nginx entrega `index.html` e o React resolve
a rota. As chamadas `/api/...` usam uma localização própria no Nginx e seguem
para a API.

## 3. Comunicação entre navegador e serviços

1. O navegador abre `http://localhost:8080`.
2. O frontend usa URLs relativas como `/api/unidades?limite=1`.
3. O Nginx encaminha essas chamadas para `http://backend:8000`, mantendo `/api`.
4. O nome `backend` é resolvido pelo DNS da rede Docker da composição.

`backend:8000` é um endereço interno dos containers, não uma URL para usar no
navegador do host. Somente o frontend publica porta: `127.0.0.1:8080:80`.
O backend possui `expose: 8000`, sem publicação de porta no host. Assim, o acesso
local à API também passa pelo Nginx; não é necessário configurar CORS adicional
para esse fluxo de mesma origem.

O frontend aguarda o backend ficar saudável antes de iniciar. O Nginx utiliza
o DNS interno do Docker para resolver novamente o backend quando ele é recriado.
Backend não depende do health/startup do Redis. A URL interna é
`redis://redis:6379/0`; não há publicação da porta Redis para o host.

### Espera do Assistente IA

Somente `/api/ia/perguntar` define `proxy_read_timeout 300s`. Nas demais rotas,
o timeout de leitura continua no padrão Nginx de 60 s. Esse limite mede inatividade
entre leituras do upstream; como a IA só envia a resposta ao finalizar C7,
a espera inicial inclui todo o pipeline. Não é um deadline global da aplicação.

Os 20 s configurados nos providers valem por chamada ao modelo. Na política
`confidential` atual, até três modelos são elegíveis por passagem. Geração SQL e
síntese podem fazer duas passagens cada (uma regeneração por fluxo): o orçamento
nominal de chamadas LLM chega a `3 × 20 × 4 = 240 s`, além de SQL, estado e overhead.
Os 300 s dão margem a esse fluxo sem alterar modelos, guardrails ou suas políticas.
Isso mitiga o 504 do proxy; não torna respostas lentas mais rápidas nem garante
um limite global rígido. `proxy_connect_timeout` e `proxy_send_timeout` não mudaram.

O access log dessa rota registra somente rota fixa, status, duração total e tempos/status
do upstream. Não inclui pergunta, resposta, SQL, sessão, query string ou headers.
Um 504 no Nginx não garante cancelamento do trabalho síncrono no backend: a C7 pode
concluir auditoria/memória/cache depois que o navegador perdeu a conexão.

No incidente de 03/11/2026, o proxy registrou 504 às 14:51:15 (São Paulo), enquanto
a auditoria correlacionada por horário concluiu `answered` às 14:51:29,822.
O request_id candidato é `f05623345893469fa4a70f6d2b398895`, distinto do caso anterior
de 43,1 s (`2ec56582af2940ffb2c3ef3ecd4dfe7e`). O log antigo não tinha ID compartilhado
nem durações: essa correlação temporal não substitui a confirmação do trace no Logfire.
O backend pode registrar HTTP 200 mesmo quando o proxy entregou 504; busque pelo
request_id/horário, não apenas pelo status HTTP do span do backend.

Os logs registraram Gemini timeout às 14:50:35,493, Cohere timeout às 14:50:55,539,
outro Gemini timeout às 14:51:18,628 e Cohere `invalid_output` às 14:51:27,534.
O intervalo entre as duas primeiras falhas foi 20,046 s, coerente com o timeout
individual. Não há duração de cada tentativa bem-sucedida nos logs antigos, nem
confirmação de leitura do trace específico; o token disponível não permite consultar
o projeto. A estimativa de 74,4 s até C7 vem de 60 s de espera mais 14,4 s após o 504,
não de uma medição recuperada do span do pipeline.

Para reduzir latência, medir p50/p95 por etapa e modelo, observar HIT/MISS do cache
com a chave atual de sessão/contexto e reduzir schema/contexto e resultados enviados
aos modelos apenas com equivalência validada. Mudanças na ordem dos modelos, seus
timeouts, um deadline global e cancelamento ao desconectar exigem avaliação separada:
podem perder respostas que hoje seriam recuperadas por fallback e precisam preservar C7.

Validação após o ajuste: `nginx -t` passou; uma rede Docker isolada com a mesma imagem
do proxy e upstream sintético atrasado em 65 s devolveu HTTP 200 em 65,048 s, sem
marcadores de conteúdo sensível no access log. Esse ensaio não substitui os providers
da aplicação. A nova chamada pela API, com providers/Gold reais e sessão nova, devolveu
HTTP 200/`ok` em 27,374 s (proxy: 27,277 s); C7 registrou `answered`, MISS, uma linha e
nenhuma regeneração, request_id `81dcfa869fe849b2b25bdd05acf56af2`.
A variação de duração não foi atribuída a uma otimização do pipeline. A suíte do
backend passou com 1.724 aprovados/19 ignorados, e os 75 testes do frontend passaram.

## 4. Bancos e caminhos

| Característica | `gold.db` | `portal.db` |
|---|---|---|
| Finalidade | Banco analítico produzido pela camada de Dados; fonte para o portal e as consultas da IA | Banco operacional com registros criados pela aplicação, como ordens de inspeção |
| Formato | SQLite | SQLite |
| Origem | Arquivo no host: `data/gold/gold.db` | Volume Docker `portal_data` |
| Caminho no backend | `/data/gold/gold.db` | `/data/portal/portal.db` |
| Montagem | Diretório `./data/gold` → `/data/gold`, bind mount somente leitura | Volume `portal_data` → `/data/portal`, leitura e escrita |
| Gestão | Snapshot publicado pelo time de Dados | Arquivo/tabelas inicializados pelo armazém operacional quando utilizado |

A separação permite atualizar a Gold sem apagar ordens e impede o backend de
alterar o snapshot analítico. O backend também abre suas conexões à Gold com
`mode=ro`. O diretório operacional inteiro é gravável para permitir as operações
do SQLite e seus arquivos auxiliares.

A Gold **não é versionada**: `data/` está no `.gitignore`. Ela também não entra
na imagem: os contextos de build são `backend/` e `frontend/`, enquanto o snapshot
fica em `data/gold/`. Os arquivos `.dockerignore` excluem bancos e configurações
locais dos contextos.

Estas variáveis já estão configuradas no Compose; não precisam ser exportadas
manualmente para executar a aplicação:

```text
DATA_SOURCE=sqlite
SQLITE_PATH=/data/gold/gold.db
PORTAL_DB_PATH=/data/portal/portal.db
REDIS_URL=redis://redis:6379/0
CACHE_TTL_SECONDS=300
CACHE_TIMEOUT_SECONDS=1
MEMORY_TTL_SECONDS=86400
MEMORY_TIMEOUT_SECONDS=1
```

`GOLD_DATA_VERSION` deve ser fornecida explicitamente e identificar o snapshot
montado. Com cache habilitado, versão ausente/em branco impede a inicialização
do backend. Não se calcula hash do banco por requisição nem versão por mtime.
Fora do Compose, omitir `REDIS_URL` desabilita o cache.

Redis não preserva cache/memória após recriação: RDB/AOF ficam desabilitados e
`/data` usa tmpfs, substituindo o volume implícito da imagem. Nenhum volume
Redis é adicionado; `portal_data` continua sendo o único volume persistente.
Auditoria é gravada na tabela `agent_audit` desse portal.db, sem tocar a Gold.
`MEMORY_TTL_SECONDS` renova a validade da sessão a cada append; o timeout de
memória é finito. Falha de leitura causa UNAVAILABLE e bypass de cache, e a
resposta continua. A C7 e seus testes reais estão em
[C7-finalizacao.md](../backend/app/agent/docs/C7-finalizacao.md).

## 5. Pré-requisitos e preparação

- Docker Desktop instalado e em execução, com engine de containers Linux.
- Docker Compose v2 com suporte a `--wait`.
- Porta local 8080 disponível.
- Repositório disponível e terminal aberto na sua raiz, onde está `compose.yaml`.
- Snapshot real recebido do time de Dados em `data/gold/gold.db`.
- Acesso aos registros de imagens e repositórios de dependências no primeiro build.

Node e Python não precisam estar instalados no host para subir a composição:
os builds e processos usam as imagens Docker. Não são necessárias credenciais
de providers para abrir o portal e consultar as rotas Gold já suportadas.

Para o Assistente IA, as chaves `GEMINI_API_KEY` e `OPENROUTER_API_KEY` precisam chegar
ao ambiente do backend. Para observabilidade, configure `LOGFIRE_ENABLED=true`,
`LOGFIRE_TOKEN` e, opcionalmente, `LOGFIRE_SERVICE_NAME`/`LOGFIRE_BASE_URL`.
O Compose repassa somente essas variáveis explicitamente; ter `backend/.env` no host
não basta. Ele não é incluído na imagem nem montado no container.

Se recebeu um ZIP, extraia o `gold.db` original para `data/gold/gold.db` antes
de subir a aplicação. Não crie um banco vazio nem copie o snapshot para o código
ou para as imagens. Confira os pré-requisitos em PowerShell:

```powershell
docker version
docker info --format '{{.OSType}}'
docker compose version

if (-not (Test-Path -LiteralPath data/gold/gold.db -PathType Leaf)) {
    throw "Gold não encontrada em data/gold/gold.db"
}

git check-ignore -v data/gold/gold.db
docker compose config --quiet
```

`docker version` deve mostrar cliente e servidor; `OSType` deve ser `linux`.
O arquivo Gold deve existir e estar ignorado pelo Git. O Compose usa
`create_host_path: false`: se `data/gold/` não existir, a montagem falha em vez
de criar silenciosamente um diretório vazio.

## 6. Primeira execução

Na raiz do repositório:

```powershell
$env:GOLD_DATA_VERSION = '2026-06-v1' # Exemplo: use a versão real do snapshot.
docker compose up --detach --build --wait
```

Para usar as credenciais e a versão Gold já configuradas em `backend/.env`, execute:

```powershell
docker compose --env-file backend/.env up --detach --build --wait
```

Use o mesmo `--env-file backend/.env` nas próximas recriações com `up`. Variáveis do
terminal têm precedência sobre esse arquivo. Não exiba `docker compose config` sem
`--quiet` com credenciais carregadas: a saída renderizada inclui seus valores.

Abra:

```text
http://localhost:8080
```

Confira o estado:

```powershell
docker compose ps
```

O resultado esperado é `backend` e `redis` com estado **healthy**, e `frontend` em execução
(**running**, normalmente mostrado como `Up`). O frontend não possui health check
próprio; não espere a indicação `healthy` para ele.

O comando constrói as imagens, cria a rede e o volume quando necessário e inicia
os serviços em segundo plano. O health check do backend consulta `/api/health`
e exige `status=ok` e `data_source=sqlite`. Isso verifica HTTP e configuração;
não abre a Gold nem testa escrita no portal. Valide uma consulta real conforme
a seção 12, mesmo quando o backend estiver saudável.

## 7. Logs

```powershell
# Todos os serviços; Ctrl+C encerra somente o acompanhamento
docker compose logs --follow --tail 100

# Logs individuais
docker compose logs --follow --tail 100 backend
docker compose logs --follow --tail 100 frontend
docker compose logs --follow --tail 100 redis

# Últimas mensagens sem acompanhamento contínuo
docker compose logs --tail 100 backend frontend redis
```

Use os logs do backend para erros de API, SQLite e exceções Python. Os logs do
frontend mostram requisições ao Nginx e falhas de proxy, como respostas 502/504.

## 8. Parada, atualização e reconstrução

Para parar e remover os containers e a rede da composição:

```powershell
docker compose down
```

**Esse comando preserva o volume `portal_data` e o arquivo Gold no host.**
Para reconstruir após mudanças e voltar a executar:

```powershell
docker compose up --detach --build --wait
```

Para recriar os containers sem solicitar um novo build:

```powershell
docker compose up --detach --force-recreate --wait
```

Se houver um motivo específico para ignorar o cache de build:

```powershell
docker compose build --no-cache
docker compose up --detach --wait
```

**Atenção: `docker compose down -v` (ou `--volumes`) remove os volumes da
composição e pode apagar os dados operacionais persistidos no `portal.db`.**
Não use essa opção para uma parada normal, rebuild ou diagnóstico.

## 9. Persistência do banco operacional

O ciclo de vida dos dados é separado do ciclo dos containers:

```text
Backend removido → portal_data permanece → novo backend monta o mesmo volume
                                         → portal.db e ordens permanecem
```

Com o nome de projeto definido no Compose, o volume se chama
`v-energy-grid-360_portal_data`. Mantenha o projeto `v-energy-grid-360`;
usar `-p` ou `COMPOSE_PROJECT_NAME` com outro nome pode selecionar outro volume
e fazer a aplicação parecer vazia, mesmo com o volume original preservado.

A Gold não depende desse volume: vem do bind mount de `data/gold/` no host e
continua disponível após remover containers. Já `portal.db` fica no armazenamento
gerenciado pelo Docker, não em `data/gold/` nem dentro da imagem.

Persistência não substitui backup: exclusão manual do volume ou remoção dos dados
do Docker Desktop pode apagar o banco operacional. Não remova volumes para
resolver problemas de inicialização.

## 10. Segurança, integridade e atualização da Gold

O bind mount define `read_only: true` para todo `/data/gold`. O backend não deve
alterar conteúdo ou schema da Gold. Ela fica separada do diretório operacional,
que precisa permanecer gravável.

Para conferir os mounts sem alterar dados:

```powershell
docker inspect v-energy-grid-360-backend-1 --format '{{json .Mounts}}'
```

Espere `/data/gold` com `Type=bind` e `RW=false`, e `/data/portal` com
`Type=volume`, nome `v-energy-grid-360_portal_data` e `RW=true`.

Uma atualização da Gold é publicada **fora do container**, substituindo o
snapshot no host. Para evitar trocar um arquivo enquanto uma consulta o lê:

1. Valide o novo snapshot e preserve a versão anterior fora do container.
2. Execute `docker compose down`, sem `-v`.
3. Substitua `data/gold/gold.db` pelo novo snapshot completo, mantendo o caminho.
4. Atualize `GOLD_DATA_VERSION` para identificar o novo snapshot e execute
   `docker compose up --detach --build --wait` e a validação rápida.

O volume operacional permanece durante esse procedimento. Não publique um
snapshot ainda em escrita ou que dependa de arquivos de journal/WAL ausentes.
Nunca corrija a Gold por comandos de escrita dentro do backend.

## 11. Mocks e testes automatizados

`MockRepository`, fixtures e mocks continuam no código porque testes automatizados
dependem deles. Eles não representam a fonte de dados do ambiente operacional:
**o Compose e a imagem backend usam `DATA_SOURCE=sqlite`**. A existência dessas
estruturas de teste não exige um Compose alternativo nem um container adicional.

## 12. Validação rápida

Após subir a aplicação, confira:

- [ ] `docker compose ps`: backend saudável e frontend em execução.
- [ ] Redis saudável e sem publicação de porta no host.
- [ ] `http://localhost:8080`: frontend abre.
- [ ] `/api/health`: HTTP 200 com `status=ok`.
- [ ] A resposta do health informa `data_source=sqlite`.
- [ ] Uma consulta de unidades retorna cadastro da Gold.

```powershell
docker compose ps
Invoke-WebRequest http://localhost:8080
Invoke-RestMethod http://localhost:8080/api/health
Invoke-RestMethod 'http://localhost:8080/api/unidades?limite=1'
```

A última chamada deve retornar uma lista com uma UC do snapshot. Ela exercita
o proxy, o repositório SQLite e a leitura real da Gold; o health isolado não
comprova essa integração.

A validação controlada da C2 com Redis real (MISS/SET/HIT, expiração, payload
inválido e Redis desligado) está descrita em
[C2-cache.md](../backend/app/agent/docs/C2-cache.md). Ela usa geração/síntese
determinísticas e mantém SQL, guardrails, C6 e Redis reais, sem credenciais de
providers. Na validação, parar somente Redis preservou o backend saudável e a
entrega das respostas; Redis foi religado ao final.

## 13. Limitações atuais

Estas são pendências da aplicação, não falhas da Dockerização:

- O repositório SQLite ainda não implementa faturamento/consumo, atendimentos e
  ocorrências/indicadores de continuidade. Rotas que dependem dessas leituras,
  como a visão 360, podem responder HTTP 501 mesmo com tabelas presentes na Gold.
- Não existem rotas HTTP individuais para detalhe cadastral, medidor e GD;
  esses métodos estão disponíveis no repositório.
- A fila sem filtro excedeu o timeout de 30 segundos na validação. O backend
  busca cada UC separadamente e usa `COLLATE NOCASE` com varredura da `dim_uc`.
  A fila filtrada com `prob_minima=1&tamanho=3` respondeu HTTP 200.
- A rota de perguntas usa o pipeline C1–C7. O Compose repassa as chaves de providers
  quando fornecidas pelo ambiente ou por `--env-file backend/.env`. Health HTTP 200
  não valida as credenciais: elas precisam ser verificadas com uma pergunta real.
  A validação C2 controlada anterior não comprova chamadas a LLMs autenticados.
- Cache C2, memória curta Redis e auditoria SQLite C7 estão integrados.
  Logfire é opcional e usa as variáveis explícitas do Compose; a política e os limites
  de validação estão em [observabilidade.md](../backend/docs/observabilidade.md).

Limites do ambiente Docker atual: acesso local por HTTP em loopback, usuário
padrão da imagem backend e dependências Python/tags base não totalmente fixadas.
TLS, exposição externa e endurecimento para produção exigem outra etapa.

## 14. Troubleshooting

Comece por `docker compose ps`, `docker compose logs --tail 100 backend frontend`
e `docker compose config --quiet`. Não use exclusão de volumes ou restauração de fábrica
como primeira tentativa de diagnóstico.

| Problema | Verificação e próximo passo |
|---|---|
| `gold.db` ausente | Execute `Test-Path -LiteralPath data/gold/gold.db -PathType Leaf`. Confira se a extração não criou subpastas extras. Coloque o snapshot original no caminho esperado e execute novamente o comando de subida. Um diretório ausente impede o bind mount; um diretório existente sem o arquivo pode permitir health saudável, mas as consultas falharão. |
| Docker Desktop/engine Linux não iniciado | Confira `docker version` e `docker info --format '{{.OSType}}'`. Se não houver servidor ou aparecer erro do pipe `dockerDesktopLinuxEngine`, inicie o Desktop, selecione containers Linux e aguarde o engine. Consulte os logs/diagnóstico do Desktop se a inicialização falhar; não apague volumes. |
| Porta 8080 ocupada | No Windows, use `Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue` e `docker ps --format 'table {{.Names}}\t{{.Ports}}'` para identificar o processo/container. Libere a porta encerrando somente o recurso identificado e dispensável; o Compose publica `127.0.0.1:8080`. |
| Backend `unhealthy` | Leia `docker compose logs --tail 100 backend` e `docker inspect v-energy-grid-360-backend-1 --format '{{json .State.Health}}'`. Confira a resposta HTTP e `DATA_SOURCE=sqlite`. Após corrigir a causa, execute `docker compose up --detach --build --wait`. |
| Permissão ou mount incorreto | Confira `docker compose config --quiet` e `docker inspect v-energy-grid-360-backend-1 --format '{{json .Mounts}}'`. A Gold precisa existir e ser legível pelo Docker Desktop; confirme o acesso ao diretório no host. `/data/gold` deve ser read-only e `/data/portal` read-write. Não torne a Gold gravável para resolver erros no portal. |
| Frontend abre, mas `/api` falha | Confira logs dos dois serviços e se o backend está saudável. Use `http://localhost:8080/api/health`; `backend:8000` é apenas interno. HTTP 502/504 requer verificar o upstream e duração das consultas; HTTP 501 das funcionalidades pendentes tem causa na aplicação. |
| Ordens parecem ter desaparecido | Confira o nome do projeto e o volume montado em `/data/portal`. Procure o volume original com `docker volume inspect v-energy-grid-360_portal_data`. Não exclua nem recrie volumes antes de identificar qual está sendo usado. |

## 15. Diagrama da arquitetura e dos dados

```text
Host
├── Navegador: http://localhost:8080
│   └── 127.0.0.1:8080 → frontend:80 (rede Docker)
│       ├── Nginx → arquivos React + fallback SPA
│       └── /api/... → http://backend:8000/api/...
│                     └── FastAPI/Uvicorn + componentes IA
│                         ├── leitura → /data/gold/gold.db
│                         ├── leitura/escrita → /data/portal/portal.db
│                         └── cache opcional → redis:6379 (sem porta no host)
│
├── data/gold/                           [bind mount read-only]
│   └── gold.db ───────────────────────→ backend:/data/gold/gold.db
│
└── Docker volume portal_data            [read-write, persistente]
    └── portal.db ──────────────────────→ backend:/data/portal/portal.db
        Nome efetivo: v-energy-grid-360_portal_data

Containers da aplicação: frontend + backend + redis
Redis: /data em tmpfs, sem persistência. Sem containers separados para SQLite ou IA.
```
