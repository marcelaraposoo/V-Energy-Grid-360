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
| `dashboardPeriodos.ts` | Validação temporal das chamadas do Dashboard e remoção de referências desativadas |

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

A integração atende à [versão base do Dashboard](../../README.md#dashboard-executivo--versão-base).
A [Análise de Receita](../../README.md#análise-de-receita) usa `api.receita.variacao(...)`, com
os parâmetros montados por `parametrosReceita` (`features/receita/tipos.ts`).

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
As rotas `cadastro-gd` e `consumo-classes` atendem à visão geral, somente com parâmetros temporais.

A tela inicia sem referência e explicita `comparar: false`. Por exemplo:

```ts
const params = {
  atual_inicio: '2025-07',
  atual_fim: '2026-06',
  comparar: false,
}
api.dashboard.kpis({ ...params, indicador: 'executivo' }, signal)
```

Com `comparar: false`, nenhum `base_inicio` ou `base_fim` é enviado. Quando a comparação
está ativa, os intervalos precisam ter a mesma duração (até 12 meses) e não podem se sobrepor.
Sem comparação, são permitidos até 24 meses. O cliente valida os períodos antes de enviar;
o backend também os valida. Os limites são jul/2022–jun/2026.

Os tipos `KpisResponse`, `SeriePonto[]`, `CadastroGdResponse` e `ConsumoClassesResponse`
representam os quatro carregamentos da tela. `periodo_base` e a posição cadastral de referência
podem ser nulos. Métricas indisponíveis permanecem nulas; a interface não deve convertê-las em zero.
No KPI de inadimplência, `variacao_pp` compara os consolidados; `inadimplencia` contém o
detalhe da última competência e a completude. Não há segunda comparação da taxa final.

O padrão da tela difere das chamadas sem parâmetros do backend: a rota de KPIs mantém a
comparação do case, e a rota de série sem parâmetros temporais retorna o catálogo completo.
Para reproduzir a tela, informe seus períodos e `comparar` explicitamente.

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
| `501` | Fonte Gold sem tabela/coluna necessária ou consulta SQLite ainda não implementada |

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

Ele chama as rotas listadas no script pelo mesmo cliente e mostra `ok` ou `FALHA` em cada uma.
Não cobre automaticamente todas as rotas novas, incluindo `cadastro-gd` e `consumo-classes`.

## Quando o backend mudar

`types.ts` é mantido à mão a partir do `schemas.py`. Se uma rota ganhar ou perder campos, atualize
essa definição única e rode `npm run build` e `npm run lint`. O `smoke-api.ts` verifica as rotas
do cliente compartilhado com o backend disponível; não substitui a validação do adaptador da tela.
