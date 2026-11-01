import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

test('Dashboard escolhe barras ou linhas conforme os períodos e preserva valores mensais', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { EvolucaoChart } = await server.ssrLoadModule('/src/features/dashboard/EvolucaoChart.tsx')
    const props = { titulo: 'Receita', unidade: 'R$', atual: [0], periodoAtual: { inicio: '2026-05', fim: '2026-05' } }
    const sozinho = renderToStaticMarkup(createElement(EvolucaoChart, props))
    assert.match(sozinho, /gráfico de barras/)
    assert.match(sozinho, />mai\/2026<\/text>/)
    assert.equal((sozinho.match(/<rect[^>]*class="dashboard-chart-current"/g) ?? []).length, 1)
    assert.equal((sozinho.match(/class="dashboard-chart-bar-value"/g) ?? []).length, 1)
    assert.doesNotMatch(sozinho, /dashboard-monthly-value|NaN|Infinity|comparado|dashboard-chart-reference|<polyline/)
    const barraMensal = renderToStaticMarkup(createElement(EvolucaoChart, { ...props, atual: [2e6] }))
    const barra = barraMensal.match(/<rect x="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"[^>]*class="dashboard-chart-current"/)
    assert.ok(barra)
    assert.equal(Number(barra[1]) + Number(barra[2]) / 2, (38 + 600 - 24) / 2)
    assert.ok(Number(barra[3]) > 0)
    const comparado = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, referencia: [0], periodoReferencia: { inicio: '2025-05', fim: '2025-05' },
    }))
    assert.match(comparado, /dashboard-chart-reference/)
    assert.match(comparado, /gráfico de barras/)
    assert.match(comparado, />mai\/2026<\/text>/)
    assert.match(comparado, />mai\/2025<\/text>/)
    assert.equal((comparado.match(/class="dashboard-chart-bar-value"/g) ?? []).length, 2)
    assert.doesNotMatch(comparado, /NaN|Infinity|<polyline/)
    const mesesDiferentes = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, atual: [2e6, 1e6, 3e6, 2e6, 4e6, 1e6], referencia: [3e6, 2e6, 1e6, 2e6, 3e6, 4e6],
      periodoAtual: { inicio: '2025-01', fim: '2025-06' },
      periodoReferencia: { inicio: '2025-07', fim: '2025-12' },
    }))
    assert.match(mesesDiferentes, /gráfico de linhas/)
    assert.doesNotMatch(mesesDiferentes, /<rect[^>]*class="dashboard-chart-(current|reference)"/)
    const rotulos = Array.from(mesesDiferentes.matchAll(/<text[^>]*class="dashboard-chart-axis"[^>]*>(.*?)<\/text>/g), (m) => m[1])
    assert.deepEqual(rotulos, ['Mês 1', 'Mês 2', 'Mês 3', 'Mês 4', 'Mês 5', 'Mês 6'])
    assert.match(mesesDiferentes, /Receita: jan\/2025, comparado a jul\/2025/)
    assert.match(mesesDiferentes, /Receita: jun\/2025, comparado a dez\/2025/)
    const curvas = Array.from(mesesDiferentes.matchAll(/<polyline[^>]*points="([^"]+)"[^>]*class="dashboard-chart-line dashboard-chart-(reference|current)"/g),
      (m) => ({ serie: m[2], pontos: m[1].split(' ').map((p) => p.split(',').map(Number)) }))
    assert.equal(curvas.length, 2)
    assert.equal(curvas[0].pontos.length, 6)
    assert.deepEqual(curvas[0].pontos.map(([x]) => x), curvas[1].pontos.map(([x]) => x))
    const curvaAtual = curvas.find((c) => c.serie === 'current')!.pontos
    assert.ok(curvaAtual[1][1] > curvaAtual[0][1]) // O segundo valor cai: não é acumulado progressivo.
    assert.ok(curvaAtual[2][1] < curvaAtual[0][1])

    const mesmosMeses = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, atual: [2e6, 1e6, 3e6, 2e6], referencia: [3e6, 2e6, 1e6, 2e6],
      periodoAtual: { inicio: '2025-12', fim: '2026-03' },
      periodoReferencia: { inicio: '2022-12', fim: '2023-03' },
    }))
    const rotulosMesmosMeses = Array.from(mesmosMeses.matchAll(/<text[^>]*class="dashboard-chart-axis"[^>]*>(.*?)<\/text>/g), (m) => m[1])
    assert.deepEqual(rotulosMesmosMeses, ['dez', 'jan', 'fev', 'mar'])
    assert.match(mesmosMeses, /Receita: dez\/2025, comparado a dez\/2022/)
    assert.match(mesmosMeses, /Receita: mar\/2026, comparado a mar\/2023/)

    const longo = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, atual: Array.from({ length: 24 }, (_, i) => 1e6 + i * 10000),
      periodoAtual: { inicio: '2024-07', fim: '2026-06' },
    }))
    assert.match(longo, /gráfico de linhas/)
    assert.equal((longo.match(/<polyline/g) ?? []).length, 1)
    assert.equal((longo.match(/<circle/g) ?? []).length, 24)
    const rotulosLongos = Array.from(longo.matchAll(/<text[^>]*class="dashboard-chart-axis"[^>]*>(.*?)<\/text>/g), (m) => m[1])
    assert.ok(rotulosLongos.length < 24)
    assert.equal(rotulosLongos[0], 'jul/24')
    assert.equal(rotulosLongos.at(-1), 'jun/26')

    const doisMeses = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, atual: [0, 1e6], periodoAtual: { inicio: '2026-01', fim: '2026-02' },
    }))
    assert.equal((doisMeses.match(/<polyline/g) ?? []).length, 1)
    assert.doesNotMatch(doisMeses, /NaN|Infinity/)
    const semReferencia = renderToStaticMarkup(createElement(EvolucaoChart, {
      ...props, periodoReferencia: { inicio: '2025-05', fim: '2025-05' },
    }))
    assert.match(semReferencia, /Sem dados para comparação/)
    assert.doesNotMatch(semReferencia, /dashboard-chart-current/)
    const { DashboardPage } = await server.ssrLoadModule('/src/features/dashboard/DashboardPage.tsx')
    const pagina = renderToStaticMarkup(createElement(DashboardPage))
    const filtros = pagina.match(/<form\b[^>]*aria-label="Filtros do dashboard"[^>]*>(.*?)<\/form>/)?.[1]
    assert.ok(filtros)
    assert.equal((filtros.match(/class="filter-field dashboard-period-picker"/g) ?? []).length, 2)
    assert.doesNotMatch(filtros, /Município|Bairro|Classe de consumo/)
    assert.match(pagina, /Período de referência \(opcional\)/)
    assert.match(pagina, /Selecionar período/)
    assert.doesNotMatch(pagina, /Remover período de referência|dashboard-kpi-comparison|dashboard-chart-reference/)
    assert.doesNotMatch(pagina, /dashboard-period-chip/)
    assert.doesNotMatch(pagina, /type="checkbox"/)
    assert.match(pagina, /Jul\/2025 a Jun\/2026/)
    const { SeletorPeriodo } = await server.ssrLoadModule('/src/features/dashboard/SeletorPeriodo.tsx')
    const vazio = renderToStaticMarkup(createElement(SeletorPeriodo, {
      label: 'Referência (opcional)', valor: null, minimo: '2022-07', maximo: '2026-06',
      onLimpar: () => {}, onChange: () => {},
    }))
    assert.match(vazio, /Selecionar período/)
    assert.doesNotMatch(vazio, /Remover período de referência|disabled=""/)
  } finally {
    await server.close()
    httpServer.close()
  }
})
