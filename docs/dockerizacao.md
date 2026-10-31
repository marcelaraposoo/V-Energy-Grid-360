# Dockerização

## Execução local

Pré-requisito: Docker Desktop em execução, usando containers Linux e Docker
Compose v2 com suporte a `--wait`. Execute os comandos na raiz do repositório.
A porta local 8080 precisa estar livre.

```powershell
# Construir e subir frontend e backend
docker compose up --detach --build --wait

# Acompanhar logs (Ctrl+C encerra somente o acompanhamento)
docker compose logs --follow --tail 100

# Consultar o estado dos serviços
docker compose ps

# Parar e remover os containers e a rede da composição
docker compose down
```

Acesse o portal em [http://localhost:8080](http://localhost:8080).
Para conferir o proxy da API:

```powershell
Invoke-RestMethod http://localhost:8080/api/health
```

A resposta deve indicar `status=ok` e `data_source=mock`.

## Execução com a Gold SQLite

O override `compose.gold.yaml` usa o snapshot real, sem incluí-lo na imagem.
Extraia o `gold.db` recebido para `data/gold/gold.db`: o diretório `data/`
está coberto pelo `.gitignore`. Não versione o banco.

```powershell
# Validar a composição efetiva e subir os serviços em modo SQLite
docker compose -f compose.yaml -f compose.gold.yaml config
docker compose -f compose.yaml -f compose.gold.yaml up --detach --build --wait

Invoke-RestMethod http://localhost:8080/api/health

# Recriar os containers preservando a Gold e o volume operacional
docker compose -f compose.yaml -f compose.gold.yaml up --detach --force-recreate --wait
```

O health check deve indicar `status=ok` e `data_source=sqlite`. Use os dois
arquivos Compose em todos os comandos dessa execução, inclusive `logs`, `ps`
e `down`, para manter a mesma configuração.

- `DATA_SOURCE=sqlite` e `SQLITE_PATH=/data/gold/gold.db` no backend.
- O diretório `./data/gold` é um bind mount **somente leitura** em `/data/gold`.
  Para usar outro diretório local, defina `GOLD_DATA_DIR` antes dos comandos.
  O diretório precisa existir; o Compose não cria um diretório vazio no lugar
  de um caminho ausente.
- `PORTAL_DB_PATH=/data/portal/portal.db` continua no mesmo volume nomeado
  `portal_data`, com leitura e escrita. Não use `down --volumes`.
- A Gold e o banco operacional permanecem em mounts separados. Os Dockerfiles
  e os contextos de build não recebem o snapshot em `data/gold/`.
- O backend atual suporta catálogos, busca/cadastro de UC, medidor/GD pelo
  repositório e fila de inspeção. A rota de visão 360 depende também de leituras
  ainda não implementadas; HTTP 501 nessas funcionalidades é uma limitação da
  aplicação, mesmo quando as tabelas já existem na Gold.
- Não existem rotas HTTP individuais para detalhe cadastral, medidor ou GD.
  Esses métodos podem ser conferidos diretamente pelo repositório dentro do
  container, sem implementar rotas novas nesta etapa.
- Na validação com a Gold recebida, a fila sem filtro excedeu o timeout de
  30 segundos do cliente. A fila com `prob_minima=1&tamanho=3` retornou HTTP 200.
  O backend busca o cadastro de cada suspeita separadamente, e a consulta com
  `COLLATE NOCASE` faz uma varredura da `dim_uc`; essa limitação de desempenho
  permanece para uma etapa funcional posterior.

## Serviços e persistência

- Sem o override Gold, a composição utiliza **`DATA_SOURCE=mock`**. Os dados
  analíticos exibidos são fictícios; não representam a Gold real.
- O frontend é o único serviço publicado pela composição:
  `127.0.0.1:8080:80`. O Nginx serve a SPA e encaminha `/api/...` para
  `http://backend:8000`, preservando o prefixo `/api`.
- O backend não publica porta no host. Seu health check consulta `/api/health`,
  e o frontend aguarda o backend ficar saudável antes de iniciar.
- `PORTAL_DB_PATH=/data/portal/portal.db`. O diretório inteiro `/data/portal/`
  fica no volume nomeado `portal_data`, com acesso de leitura e escrita. Com o
  nome de projeto padrão, o volume Docker se chama `v-energy-grid-360_portal_data`.
- **`docker compose down` preserva o volume operacional.** Ao subir novamente
  a mesma composição, as ordens de inspeção permanecem disponíveis. Não use
  `docker compose down --volumes` nem `docker compose down -v` na parada normal:
  essas opções removem os volumes gerenciados pela composição.
- Persistência não substitui backup. A exclusão manual do volume ou dos dados
  do Docker Desktop pode apagar as ordens. Outro nome de projeto Compose pode
  selecionar um volume diferente.
- A composição mock não precisa de `.env` nem de credenciais de providers.
  Os contextos de build excluem configurações locais e bancos; não coloque
  credenciais reais no Compose ou nos Dockerfiles.

## Reconstrução e verificação

```powershell
docker compose config
docker compose build --no-cache
docker compose up --detach --wait
docker compose ps
```

O build sem cache requer acesso aos registros de imagens e aos repositórios
de dependências. Os prompts Markdown da IA pertencem a `backend/app/` e devem
continuar na imagem backend.

## Limites e pendências

- O modo padrão continua mock; o override `compose.gold.yaml` permite usar
  a Gold real com montagem somente leitura, separada do volume operacional.
  Isso não implementa as leituras da Gold ainda pendentes no backend.
- **Redis será integrado posteriormente**, quando os adapters de cache e/ou
  memória estiverem prontos e as políticas de persistência forem definidas.
  Não há serviço Redis na composição atual.
- O health check confirma a resposta HTTP e o modo escolhido; não verifica
  integridade do SQLite, capacidade de escrita, providers ou o fluxo da IA.
- A conexão completa do agente ao chat, os adapters de estado e as leituras
  Gold ainda não implementadas são pendências da aplicação, não da Dockerização.
- Este ambiente é local, com HTTP em loopback. TLS, exposição externa e
  endurecimento para produção exigem uma etapa própria. A imagem backend ainda
  usa o usuário padrão da imagem base, sem configuração de usuário sem privilégios.
- As tags das imagens base e as dependências Python não estão totalmente
  fixadas. Um novo build pode resolver versões diferentes; o frontend usa
  `package-lock.json` com `npm ci`.
