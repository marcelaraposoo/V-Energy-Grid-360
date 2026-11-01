import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'
import type { Kpi, KpisResponse, Periodo } from '../src/api/types.ts'
import { parametrosInadimplencia } from '../src/features/dashboard/inadimplencia.ts'

const periodo = { inicio: '2026-01', fim: '2026-06' }
const referencia = { inicio: '2025-01', fim: '2025-06' }
const kpi: Kpi = {
  nome: 'Inadimplência', unidade: '%', valor_atual: 5.8, valor_base: 4.7,
  variacao_abs: null, variacao_pct: null, variacao_pp: 1.1,
  inadimplencia: {
    ultima_competencia: '2026-06', ultima_competencia_pct: 6.2,
    competencias_ausentes: [], competencias_ausentes_base: [], data_corte: '2026-06-30',
  },
}

test('consulta da inadimplência usa somente períodos e omite referência desativada', async () => {
  const chamadas: URL[] = []
  const api = createApi(createHttp('http://test', async (url) => {
    chamadas.push(new URL(String(url)))
    return new Response(JSON.stringify({ kpis: [kpi] }))
  }))
  await api.dashboard.kpis(parametrosInadimplencia(periodo, null))
  const params = chamadas[0].searchParams
  assert.equal(chamadas[0].pathname, '/api/dashboard/kpis')
  assert.equal(params.get('indicador'), 'inadimplencia')
  assert.equal(params.get('comparar'), 'false')
  assert.equal(params.get('atual_inicio'), '2026-01')
  assert.equal(params.get('atual_fim'), '2026-06')
  assert.equal(params.has('base_inicio'), false)
  assert.equal(params.has('base_fim'), false)
  await api.dashboard.kpis(parametrosInadimplencia(periodo, referencia))
  assert.equal(chamadas[1].searchParams.get('base_inicio'), '2025-01')
  assert.equal(chamadas[1].searchParams.get('base_fim'), '2025-06')
  assert.equal(chamadas[1].searchParams.get('comparar'), 'true')
  await api.dashboard.kpis(parametrosInadimplencia(periodo, null))
  assert.equal(chamadas[2].searchParams.has('base_inicio'), false)
  assert.throws(() => api.dashboard.kpis(parametrosInadimplencia(periodo, { inicio: '2026-02', fim: '2026-03' })))
  assert.equal(chamadas.length, 3)
  for (const chamada of chamadas) {
    for (const filtro of ['municipio', 'bairro', 'classe']) assert.equal(chamada.searchParams.has(filtro), false)
  }
})

test('card de faturamento em aberto respeita mês, consolidado, comparação e indisponibilidade', async (t) => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { InadimplenciaCard } = await server.ssrLoadModule('/src/features/dashboard/InadimplenciaCard.tsx')
    function renderizar(atual: Periodo, base: Periodo | null, indicador: Kpi = kpi) {
      const data: KpisResponse = { periodo_atual: atual, periodo_base: base, kpis: [indicador] }
      return renderToStaticMarkup(createElement(InadimplenciaCard, {
        periodo: atual, referencia: base, estado: { data, loading: false, error: null, reload: () => {} },
      }))
    }
    await t.test('mês sem comparação mostra somente a taxa mensal', () => {
      const html = renderizar({ inicio: '2026-06', fim: '2026-06' }, null)
      assert.match(html, /Faturamento em aberto/)
      assert.match(html, /5,8<small>%<\/small>/)
      assert.match(html, /Competência · Jun\/2026/)
      assert.equal((html.match(/<small>%<\/small>/g) ?? []).length, 1)
      assert.doesNotMatch(html, /Última competência|Consolidado|p\.p\.|Faturas em aberto/)
    })
    await t.test('mês × mês mostra somente uma taxa e uma variação em pp', () => {
      const html = renderizar({ inicio: '2026-06', fim: '2026-06' }, { inicio: '2025-06', fim: '2025-06' })
      assert.match(html, /\+1,1 p\.p\./)
      assert.match(html, /vs\. referência · Jun\/2025/)
      assert.equal((html.match(/<small>%<\/small>/g) ?? []).length, 1)
      assert.doesNotMatch(html, /Última competência/)
    })
    await t.test('intervalo sem comparação destaca consolidado e identifica a última competência', () => {
      const html = renderizar(periodo, null)
      assert.match(html, /Consolidado · Jan–Jun\/2026/)
      assert.match(html, /6,2<small>%<\/small>/)
      assert.match(html, /Última competência · Jun\/2026/)
      assert.equal((html.match(/<small>%<\/small>/g) ?? []).length, 2)
      assert.doesNotMatch(html, /p\.p\.|vs\./)
    })
    await t.test('período × período mantém uma única comparação junto ao consolidado', () => {
      const html = renderizar(periodo, referencia)
      assert.match(html, /vs\. referência · Jan–Jun\/2025/)
      assert.equal((html.match(/p\.p\./g) ?? []).length, 1)
      assert.ok(html.indexOf('p.p.') < html.indexOf('Última competência'))
      assert.match(html, /Situação conhecida até 30\/06\/2026/)
    })
    await t.test('lacuna não esconde a última taxa disponível e não mostra pp inválidos', () => {
      const html = renderizar(periodo, referencia, { ...kpi, valor_atual: null })
      assert.match(html, /Indisponível/)
      assert.match(html, /6,2<small>%<\/small>/)
      assert.doesNotMatch(html, /p\.p\./)
      const semBase = renderizar(periodo, referencia, { ...kpi, valor_base: null })
      assert.match(semBase, /5,8<small>%<\/small>/)
      assert.doesNotMatch(semBase, /p\.p\./)
    })
    await t.test('último mês ausente também fica indisponível; zero continua sendo um valor', () => {
      const semFinal = renderizar(periodo, null, {
        ...kpi, valor_atual: null, inadimplencia: { ...kpi.inadimplencia!, ultima_competencia_pct: null },
      })
      assert.equal((semFinal.match(/Indisponível/g) ?? []).length, 2)
      const zero = renderizar(periodo, referencia, {
        ...kpi, valor_atual: 0, valor_base: 0, variacao_pp: 0,
        inadimplencia: { ...kpi.inadimplencia!, ultima_competencia_pct: 0 },
      })
      assert.equal((zero.match(/0,0<small>%<\/small>/g) ?? []).length, 2)
      assert.match(zero, /0,0 p\.p\./)
      assert.doesNotMatch(zero, /Indisponível/)
    })
    await t.test('loading, erro e resposta vazia não apresentam valores antigos', () => {
      const props = { periodo, referencia, estado: { data: { kpis: [kpi] }, loading: true, error: null, reload: () => {} } }
      const carregando = renderToStaticMarkup(createElement(InadimplenciaCard, props))
      assert.match(carregando, /Carregando faturamento em aberto/)
      assert.doesNotMatch(carregando, /5,8|6,2|p\.p\./)
      const erro = renderToStaticMarkup(createElement(InadimplenciaCard, {
        ...props, estado: { ...props.estado, loading: false, error: new Error('Falha na consulta') },
      }))
      assert.match(erro, /Tentar novamente/)
      assert.doesNotMatch(erro, /5,8|6,2|p\.p\./)
      const vazio = renderToStaticMarkup(createElement(InadimplenciaCard, {
        ...props, estado: { ...props.estado, loading: false, data: { kpis: [] } },
      }))
      assert.match(vazio, /Indisponível/)
      assert.doesNotMatch(vazio, /p\.p\./)
    })
  } finally {
    await server.close()
    httpServer.close()
  }
})
