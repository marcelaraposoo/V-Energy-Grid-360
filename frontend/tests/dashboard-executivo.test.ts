import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'
import type { CadastroGdResponse, ConsumoClassesResponse, KpisResponse, SeriePonto } from '../src/api/types.ts'
import { parametrosDashboard, valoresMensais } from '../src/features/dashboard/consultas.ts'
import { escalaGrafico, unidadeDaEscala } from '../src/features/dashboard/escalaGrafico.ts'

const periodo = { inicio: '2026-01', fim: '2026-02' }
const referencia = { inicio: '2025-01', fim: '2025-02' }

test('eixo Y usa faixa dos dados e a mesma unidade indicada no gráfico', () => {
  const pequena = escalaGrafico([10, 20])
  assert.equal(pequena.maximo, 20)
  assert.deepEqual(pequena.marcacoes, [0, 5, 10, 15, 20])
  assert.equal(unidadeDaEscala('R$', pequena.prefixo), 'R$')
  const mil = escalaGrafico([120000, 250000])
  assert.equal(mil.maximo, 250000)
  assert.equal(mil.divisor, 1000)
  assert.equal(unidadeDaEscala('kWh', mil.prefixo), 'mil kWh')
  const comparada = escalaGrafico([100, 200, 1200, 900])
  assert.ok(comparada.maximo >= 1200)
  const milhoes = escalaGrafico([22e6])
  assert.equal(unidadeDaEscala('R$', milhoes.prefixo), 'R$ milhões')
  assert.equal(unidadeDaEscala('kWh', milhoes.prefixo), 'milhões de kWh')
  const zerada = escalaGrafico([0, 0])
  assert.ok(zerada.maximo > 0)
  assert.ok(zerada.marcacoes.every(Number.isFinite))
  assert.equal(escalaGrafico([0.01]).casas, 3)
})

test('consultas da visão executiva preservam comparação opcional e enviam somente períodos', async () => {
  const urls: URL[] = []
  const sinais: (AbortSignal | null | undefined)[] = []
  const api = createApi(createHttp('http://test', async (url, init) => {
    urls.push(new URL(String(url))); sinais.push(init?.signal)
    return new Response(JSON.stringify({}))
  }))
  const controller = new AbortController()
  for (const base of [null, referencia]) {
    const params = parametrosDashboard(periodo, base)
    await api.dashboard.kpis({ ...params, indicador: 'executivo' }, controller.signal)
    await api.dashboard.serie(params, controller.signal)
    await api.dashboard.cadastroGd(params, controller.signal)
    await api.dashboard.consumoClasses(params, controller.signal)
  }
  assert.deepEqual(urls.slice(0, 4).map((url) => url.pathname), [
    '/api/dashboard/kpis', '/api/dashboard/serie', '/api/dashboard/cadastro-gd', '/api/dashboard/consumo-classes',
  ])
  urls.forEach((url, i) => {
    assert.equal(url.searchParams.get('atual_inicio'), '2026-01')
    assert.equal(url.searchParams.get('comparar'), i < 4 ? 'false' : 'true')
    assert.equal(url.searchParams.has('base_inicio'), i >= 4)
    for (const filtro of ['municipio', 'bairro', 'classe']) assert.equal(url.searchParams.has(filtro), false)
    assert.equal(sinais[i], controller.signal)
  })
  assert.equal(urls[0].searchParams.get('indicador'), 'executivo')
  assert.throws(() => api.dashboard.consumoClasses(parametrosDashboard(periodo, periodo)))
  assert.equal(urls.length, 8)
})

test('adaptador mensal preserva meses reais, zeros e lacunas por métrica', () => {
  const serie: SeriePonto[] = [
    { competencia: '2026-02', receita: 200, energia_kwh: 100, tarifa_media: 2 },
    { competencia: '2025-01', receita: 99, energia_kwh: 99, tarifa_media: 1 },
    { competencia: '2026-01', receita: 0, energia_kwh: null, tarifa_media: null },
  ]
  assert.deepEqual(valoresMensais(serie, periodo, 'receita'), [0, 200])
  assert.equal(valoresMensais(serie, periodo, 'energia_kwh'), null)
  assert.equal(valoresMensais(serie, referencia, 'receita'), null)
})

test('componentes executivos mostram três KPIs, cadastro/GD e uma barra por classe', async (t) => {
  const httpServer = createHttpServer()
  const server = await createServer({ configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null } })
  const estado = <T,>(data: T) => ({ data, loading: false, error: null, reload: () => {} })
  try {
    const { KpisPrincipais } = await server.ssrLoadModule('/src/features/dashboard/KpisPrincipais.tsx')
    const { UcsGdCard } = await server.ssrLoadModule('/src/features/dashboard/UcsGdCard.tsx')
    const { ClassesChart } = await server.ssrLoadModule('/src/features/dashboard/ClassesChart.tsx')
    const { EvolucaoPanel } = await server.ssrLoadModule('/src/features/dashboard/EvolucaoPanel.tsx')
    const kpis: KpisResponse = { periodo_atual: periodo, periodo_base: referencia,
      kpis: ['Receita faturada', 'Energia faturada', 'Tarifa média efetiva', 'UCs faturadas'].map((nome) => ({
        nome, unidade: '', valor_atual: 200, valor_base: 100, variacao_abs: 100, variacao_pct: 100,
      })) }
    const cadastro: CadastroGdResponse = { atual: { competencia: '2026-02', qtd_ucs_cadastradas: 120, qtd_ucs_com_gd: 18, percentual_gd: 15 },
      referencia: { competencia: '2025-02', qtd_ucs_cadastradas: 100, qtd_ucs_com_gd: 10, percentual_gd: 10 }, variacao_cadastradas_pct: 20 }
    const classes: ConsumoClassesResponse = { periodo_atual: periodo, periodo_base: referencia, consumo_total_kwh: 1000,
      classes: ['RESIDENCIAL', 'INDUSTRIAL', 'COMERCIAL', 'RURAL', 'PODER PUBLICO'].map((classe, i) => ({
        classe: classe as ConsumoClassesResponse['classes'][number]['classe'], consumo_kwh: [500, 300, 100, 60, 40][i],
        participacao_pct: [50, 30, 10, 6, 4][i], consumo_referencia_kwh: i === 2 ? 0 : 100,
        variacao_pct: i === 2 ? null : i === 1 ? -10 : 10, competencias_ausentes: [], competencias_ausentes_referencia: [],
      })) }
    await t.test('topo tem exatamente receita, consumo e preço; UCs faturadas ficam fora da tela', () => {
      const html = renderToStaticMarkup(createElement(KpisPrincipais, { estado: estado(kpis), referencia }))
      assert.equal((html.match(/class="panel kpi-card"/g) ?? []).length, 3)
      assert.match(html, /Receita de energia/)
      assert.match(html, /Energia faturada/)
      assert.match(html, /Preço médio por kWh/)
      assert.doesNotMatch(html, /UCs faturadas/)
      // Valor da referência e variação em cada card; explicações no "i", com o mesmo texto da Análise de Receita.
      assert.equal((html.match(/class="kpi-card-referencia">Referência: /g) ?? []).length, 3)
      assert.equal((html.match(/class="kpi-comparacao"/g) ?? []).length, 3)
      assert.equal((html.match(/class="info-tip-balao"/g) ?? []).length, 3)
      assert.match(html, /sem tributos e com o adicional de bandeira/)
      assert.match(html, /R\$&nbsp;200,00|R\$\s200,00/)
      const semBase = renderToStaticMarkup(createElement(KpisPrincipais, { estado: estado(kpis), referencia: null }))
      assert.doesNotMatch(semBase, /kpi-card-referencia|kpi-comparacao/)
    })
    await t.test('cadastro mostra posição final, GD e participação sem somar meses', () => {
      const html = renderToStaticMarkup(createElement(UcsGdCard, { estado: estado(cadastro), competencia: '2026-02', referencia }))
      assert.match(html, /Base em Fev\/2026/)
      assert.match(html, /120<small>UCs cadastradas/)
      assert.match(html, /18 com geração distribuída/)
      assert.match(html, /15,0%/)
      assert.match(html, /20,0%/)
      assert.match(html, /cadastradas em Fev\/2025/)
    })
    await t.test('cadastro com denominador zero ou sem competência final não inventa percentual', () => {
      const data = { ...cadastro, atual: { competencia: '2026-02', qtd_ucs_cadastradas: 0, qtd_ucs_com_gd: 0, percentual_gd: null } }
      const html = renderToStaticMarkup(createElement(UcsGdCard, { estado: estado(data), competencia: '2026-02', referencia: null }))
      assert.match(html, /0<small>UCs cadastradas/)
      assert.match(html, /Percentual indisponível/)
      assert.doesNotMatch(html, /NaN|Infinity/)
      const ausente = { ...data, atual: { ...data.atual, qtd_ucs_cadastradas: null, qtd_ucs_com_gd: null } }
      assert.match(renderToStaticMarkup(createElement(UcsGdCard, { estado: estado(ausente), competencia: '2026-02', referencia: null })), /Indisponível/)
    })
    await t.test('classes mantêm cinco barras únicas, ordem, participação e variação contextualizada', () => {
      const html = renderToStaticMarkup(createElement(ClassesChart, { estado: estado(classes), periodo, referencia }))
      assert.equal((html.match(/class="dashboard-class-bar"/g) ?? []).length, 5)
      assert.deepEqual(Array.from(html.matchAll(/data-classe="([^"]+)"/g), (m) => m[1]), classes.classes.map((c) => c.classe))
      assert.match(html, /50,0%/)
      assert.match(html, /−10,0%/)
      assert.match(html, /class="dashboard-class-change" data-tendencia="desfavoravel"/)
      assert.match(html, /Variação vs\. referência · Jan–Fev\/2025/)
      assert.doesNotMatch(html, /NaN|Infinity/)
      const semBase = renderToStaticMarkup(createElement(ClassesChart, { estado: estado(classes), periodo, referencia: null }))
      assert.doesNotMatch(semBase, /dashboard-class-change|Variação vs\./)
      assert.match(semBase, /Participação no consumo total/)
    })
    await t.test('classe incompleta informa indisponibilidade e não representa volume parcial', () => {
      const data = { ...classes, consumo_total_kwh: null, classes: classes.classes.map((c) => ({ ...c, consumo_kwh: null, participacao_pct: null, variacao_pct: null })) }
      const html = renderToStaticMarkup(createElement(ClassesChart, { estado: estado(data), periodo, referencia }))
      assert.equal((html.match(/Indisponível/g) ?? []).length, 5)
      assert.match(html, /Participação indisponível/)
      assert.doesNotMatch(html, /width:NaN|Infinity/)
    })
    await t.test('gráficos existentes continuam barras para mês e linhas para períodos', () => {
      const data: SeriePonto[] = [{ competencia: '2026-01', receita: 200, energia_kwh: null, tarifa_media: null }, { competencia: '2026-02', receita: 100, energia_kwh: 20, tarifa_media: 5 }]
      const linhas = renderToStaticMarkup(createElement(EvolucaoPanel, { estado: estado(data), periodo, referencia: null, campo: 'receita' }))
      assert.match(linhas, /gráfico de linhas/)
      const barras = renderToStaticMarkup(createElement(EvolucaoPanel, { estado: estado(data), periodo: { inicio: '2026-02', fim: '2026-02' }, referencia: null, campo: 'receita' }))
      assert.match(barras, /gráfico de barras/)
      const lacuna = renderToStaticMarkup(createElement(EvolucaoPanel, { estado: estado(data), periodo, referencia: null, campo: 'energia_kwh' }))
      assert.match(lacuna, /Sem dados para o período/)
      assert.doesNotMatch(lacuna, /<polyline/)
    })
    await t.test('loading e erro escondem dados anteriores nos novos componentes', () => {
      for (const [Component, data, props] of [
        [KpisPrincipais, kpis, { referencia }], [UcsGdCard, cadastro, { competencia: '2026-02', referencia }],
        [ClassesChart, classes, { periodo, referencia }],
      ] as const) {
        const carregando = renderToStaticMarkup(createElement(Component, { ...props, estado: { ...estado(data), loading: true } }))
        assert.match(carregando, /Carregando/)
        assert.doesNotMatch(carregando, /dashboard-class-bar|120<small>/)
        const erro = renderToStaticMarkup(createElement(Component, { ...props, estado: { ...estado(data), error: new Error('Falha') } }))
        assert.match(erro, /Tentar novamente/)
      }
    })
    await t.test('a composição posiciona complementares e classes antes da evolução mensal', async () => {
      const { DashboardPage } = await server.ssrLoadModule('/src/features/dashboard/DashboardPage.tsx')
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(DashboardPage)))
      assert.ok(html.indexOf('dashboard-kpis') < html.indexOf('dashboard-complementary'))
      assert.ok(html.indexOf('dashboard-complementary') < html.indexOf('dashboard-charts'))
      assert.match(html, /Energia faturada por classe/)
      assert.match(html, /UCs cadastradas e (GD|geração distribuída)/)
      assert.doesNotMatch(html, /Atendimento|UCs faturadas|Classe de consumo|Todos os municípios/)
    })
  } finally { await server.close(); httpServer.close() }
})
