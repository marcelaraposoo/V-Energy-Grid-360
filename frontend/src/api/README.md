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

Os tipos da Visão 360 têm uma única definição em `types.ts`, também reexportada por
`features/unidades/types.ts`. Os nomes anteriores, como `UnidadeConsumidora` e `Atendimento`,
são aliases desses tipos atuais. O contrato inclui diagnóstico por dois meses, faturas
paginadas, trocas de medidor, contexto de continuidade e atendimentos conforme a B1.

A tela da Visão 360 usa o adaptador `features/unidades/api.ts`, que compartilha esses tipos.
Ele solicita todos os atendimentos e usa a rota própria de faturas; o cliente genérico
`api.unidades.visao360(ucId, signal)` mantém os padrões do endpoint, inclusive 12 meses
para atendimentos.

## Configuração

Em desenvolvimento não precisa configurar nada: o padrão é `http://localhost:8000`.
Se o backend estiver em outro endereço, copie `frontend/.env.example` para `frontend/.env.local`
(o Git ignora esse arquivo) e ajuste `VITE_API_URL`. Reinicie o `npm run dev` depois de mudar.

## Dashboard Executivo

A tela envia somente períodos. `api.dashboard.kpis({ ...params, indicador: 'executivo' }, signal)`
retorna os KPIs principais e o faturamento em aberto sem depender da A8. O contrato padrão
sem esse parâmetro permanece disponível, incluindo UCs faturadas e os indicadores de continuidade.

- `api.dashboard.serie(params, signal)`: evolução mensal A5/A3; valores nulos não viram zero.
- `api.dashboard.cadastroGd(params, signal)`: posição cadastral A5 da última competência
  principal e de referência, participação da GD e variação percentual de UCs cadastradas.
- `api.dashboard.consumoClasses(params, signal)`: cinco classes em ordem de volume principal,
  participação, volume de referência e variação percentual, calculados no backend pela A3.

Ausência de uma classe em qualquer competência invalida seu consolidado. A participação
fica nula quando o total está incompleto ou é zero; referência zero ou ausente não produz
variação percentual. Os DTOs compartilhados em `types.ts` representam essas indisponibilidades.
As funções existentes da API continuam aceitando filtros regionais nas telas que os utilizam.

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
- As buscas da Visão 360 e do cabeçalho aceitam `000001` ou `UC000001` e convertem para
  `UC000001` antes de consultar a API. O cliente `api.unidades.visao360(ucId, signal)`
  recebe o identificador completo; essa conversão é feita pela interface.
- `api.health()` informa a fonte configurada: `mock` usa dados fictícios; `sqlite` lê o arquivo
  configurado no backend. A homologação da exportação oficial é separada dos testes com SQLite fictício.

## Testar a integração

Com o backend rodando (`uvicorn app.main:app --port 8000` dentro de `backend/`), na pasta `frontend/` (Node 24+):

```
node scripts/smoke-api.ts                 # só leitura
node scripts/smoke-api.ts --com-ordens    # também cria e conclui uma ordem de inspeção
```

Ele chama todas as rotas pelo mesmo cliente e mostra `ok` ou `FALHA` em cada uma.

## Quando o backend mudar

`types.ts` é mantido à mão a partir do `schemas.py`. Se uma rota ganhar ou perder campos, atualize
essa definição única e rode `npm run build` e `npm run lint`. O `smoke-api.ts` verifica as rotas
do cliente compartilhado com o backend disponível; não substitui a validação do adaptador da tela.
