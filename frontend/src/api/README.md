# Cliente da API (frontend → backend)

Tudo que o frontend precisa para conversar com o backend FastAPI fica nesta pasta. Não usa biblioteca
nova: é `fetch` puro, com tipos TypeScript que espelham o `backend/app/schemas.py`.

| Arquivo | Para quê |
|---|---|
| `index.ts` | Ponto de entrada: exporta `api`, `useApi`, `ApiError` e os tipos |
| `endpoints.ts` | Uma função por rota (`api.unidades.visao360(...)`, `api.perdas.fila(...)` etc.) |
| `types.ts` | Tipos das respostas e dos parâmetros |
| `http.ts` | `fetch` com tratamento de erro (`ApiError`) |
| `useApi.ts` | Hook que carrega dados de uma tela (loading, erro, cancelamento e `reload`) |

## Configuração

Em desenvolvimento não precisa configurar nada: o padrão é `http://localhost:8000`.
Se o backend estiver em outro endereço, copie `frontend/.env.example` para `frontend/.env.local`
(o Git ignora esse arquivo) e ajuste `VITE_API_URL`. Reinicie o `npm run dev` depois de mudar.

## Como usar

**Carregar dados ao abrir uma tela**

```tsx
import { useParams } from 'react-router-dom'
import { api, useApi } from '../../api'

function Visao360({ ucId }: { ucId: string }) {
  const { data, error, loading, reload } = useApi(
    (signal) => api.unidades.visao360(ucId, signal),
    [ucId],
  )

  if (loading) return <p>Carregando…</p>
  if (error) return <button onClick={reload}>{error.message} Tentar de novo</button>
  if (!data) return null
  return <h1>{data.cadastro.titular}</h1>
}

export function UnidadesPage() {
  const { id } = useParams()
  return id ? <Visao360 ucId={id} /> : <p>Busque uma unidade.</p>
}
```

**Executar uma ação (botão) e tratar o erro**

```tsx
import { api, ApiError } from '../../api'

async function enviarParaCampo(ordemId: number) {
  try {
    await api.perdas.iniciarOrdem(ordemId)
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === 409) {
      alert(erro.detail) // ex.: "A ordem 3 está CONCLUIDA e não pode ser cancelada (...)"
    } else {
      throw erro
    }
  }
}
```

**Lista paginada (fila de suspeitas)**

```tsx
const { data } = useApi(
  (signal) => api.perdas.fila({ q: busca, pagina, tamanho: 20 }, signal),
  [busca, pagina],
)
// data?.itens  -> os itens da página
// data?.total  -> total após os filtros (vem do cabeçalho X-Total-Count)
```

## Erros

Toda resposta que não for 2xx vira um `ApiError` com `status` e `detail` (texto pronto para exibir):

| `status` | Quando |
|---|---|
| `0` | Não conseguiu falar com o servidor (backend desligado, porta errada) |
| `404` | UC, ordem ou alimentador inexistente |
| `409` | Ação inválida para o estado atual (ex.: cancelar ordem concluída) |
| `422` | Parâmetro inválido (ex.: município que não existe, período invertido) |

## Convenções

- Os nomes de campos e de parâmetros são os **mesmos da API** (snake_case), para conferir com `http://localhost:8000/docs`.
- Todas as funções aceitam um `AbortSignal` como último argumento; o `useApi` já o repassa.
- No `useApi`, a lista `deps` deve ter valores simples (ids, textos, números): eles são comparados como JSON.
- `ucId` aceita `uc00001` ou `UC00001`, mas **não** só o número. Na busca global, consulte
  `api.unidades.buscar({ q })` antes de abrir a visão 360.
- Enquanto a camada Gold não estiver pronta, **todos os números são fictícios** (`api.health()` mostra `data_source: "mock"`).

## Testar a integração

Com o backend rodando (`uvicorn app.main:app --port 8000` dentro de `backend/`), na pasta `frontend/` (Node 24+):

```
node scripts/smoke-api.ts                 # só leitura
node scripts/smoke-api.ts --com-ordens    # também cria e conclui uma ordem de inspeção
```

Ele chama todas as rotas pelo mesmo cliente e mostra `ok` ou `FALHA` em cada uma.

## Quando o backend mudar

`types.ts` é mantido à mão a partir do `schemas.py`. Se uma rota ganhar ou perder campos, atualize o tipo
e rode `npm run build` (o TypeScript acusa as telas afetadas) e o `smoke-api.ts`.
