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

## Serviços e persistência

- A composição atual utiliza explicitamente **`DATA_SOURCE=mock`**. Os dados
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

- A integração com **`gold.db` real está pendente**, pois o snapshot ainda não
  foi disponibilizado. Não há montagem Gold nesta composição, nem banco Gold
  sintético substituto. A futura integração deverá validar o snapshot e montar
  seu diretório em modo somente leitura, separado do volume operacional.
- **Redis será integrado posteriormente**, quando os adapters de cache e/ou
  memória estiverem prontos e as políticas de persistência forem definidas.
  Não há serviço Redis na composição atual.
- O health check atual confirma a resposta HTTP e o modo mock; não verifica
  integridade do SQLite, capacidade de escrita, providers ou o fluxo da IA.
- A conexão completa do agente ao chat, os adapters de estado e as leituras
  Gold ainda não implementadas são pendências da aplicação, não da Dockerização.
- Este ambiente é local, com HTTP em loopback. TLS, exposição externa e
  endurecimento para produção exigem uma etapa própria. A imagem backend ainda
  usa o usuário padrão da imagem base, sem configuração de usuário sem privilégios.
- As tags das imagens base e as dependências Python não estão totalmente
  fixadas. Um novo build pode resolver versões diferentes; o frontend usa
  `package-lock.json` com `npm ci`.
