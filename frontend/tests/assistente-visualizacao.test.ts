import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer as createHttpServer } from 'node:http'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

test('gráfico e tabela são disclosures nativos independentes e recolhidos, inclusive em payload cacheado', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({ configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null } })
  try {
    const { VisualizacaoChart, formatarMesReferencia } = await server.ssrLoadModule('/src/features/assistente/VisualizacaoChart.tsx')
    assert.equal(formatarMesReferencia('2024-01'), 'jan/2024')
    assert.equal(formatarMesReferencia('2024-12'), 'dez/2024')
    assert.equal(formatarMesReferencia('2024-01-15'), '2024-01-15')
    assert.equal(formatarMesReferencia('2024-13'), '2024-13')
    assert.equal(formatarMesReferencia('Recife'), 'Recife')
    for (const type of ['bar', 'line']) {
      const spec = { type, title: 'Valor faturado', unit: 'R$', points: [{ label: '2024-01', value: 7 }, { label: '2024-03', value: 3 }] }
      const before = JSON.stringify(spec)
      const html = renderToStaticMarkup(createElement(VisualizacaoChart, { spec }))
      assert.equal((html.match(/<details/g) ?? []).length, 2)
      assert.doesNotMatch(html, /<details[^>]*\bopen(?:=|\s|>)/)
      // Fechamento do gráfico ocorre antes da abertura da tabela: irmãos, não aninhados.
      assert.ok(html.indexOf('</details>') < html.indexOf('<details class="viz-data"'))
      assert.match(html, /Ver gráfico/)
      assert.match(html, /Ocultar gráfico/)
      assert.match(html, /Ver os dados em tabela/)
      assert.match(html, /jan\/2024/)
      assert.match(html, /mar\/2024/)
      assert.match(html, /R\$ 7/)
      assert.match(html, /R\$ 3/)
      assert.equal(JSON.stringify(spec), before)
      const cached = JSON.parse(before)
      assert.equal(renderToStaticMarkup(createElement(VisualizacaoChart, { spec: cached })), html)
    }
  } finally {
    await server.close()
    httpServer.close()
  }
})
