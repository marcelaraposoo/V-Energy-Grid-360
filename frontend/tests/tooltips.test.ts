import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

test('ajudas dos cards preservam acessibilidade e as definições dos indicadores', async (t) => {
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: createHttpServer() }, watch: null },
  })
  try {
    const { InfoTip, InfoTipContent } = await server.ssrLoadModule('/src/components/ui/InfoTip.tsx')
    const { ResumoReceita } = await server.ssrLoadModule('/src/features/receita/ResumoReceita.tsx')
    const { GeracaoSection } = await server.ssrLoadModule('/src/features/unidades/components/UnidadeSections.tsx')

    await t.test('o botão identifica a explicação, que permanece oculta antes da interação', () => {
      const html = renderToStaticMarkup(createElement(InfoTip, { titulo: 'Consumo' },
        createElement(InfoTipContent, { resumo: 'Energia faturada no mês.', nota: 'Medida em kWh.' })))
      const descricao = html.match(/aria-describedby="([^"]+)"/)?.[1]
      assert.ok(descricao)
      assert.ok(html.includes(`id="${descricao}"`))
      assert.match(html, /aria-label="Sobre: Consumo"/)
      assert.match(html, /role="tooltip"[^>]*hidden=""/)
      assert.match(html, /Energia faturada no mês/)
      assert.match(html, /Medida em kWh/)
    })

    await t.test('a Receita mantém tributos fora do indicador e explica a soma dos efeitos', () => {
      const total = { receita_base: 100, receita_atual: 110, variacao_receita: 10, variacao_receita_pct: 10,
        energia_base_kwh: 100, energia_atual_kwh: 90, variacao_energia_pct: -10,
        preco_base_kwh: 1, preco_atual_kwh: 110 / 90, efeito_volume: -10, efeito_preco: 20 }
      const html = renderToStaticMarkup(createElement(ResumoReceita, { total, referencia: { inicio: '2025-01', fim: '2025-01' } }))
      assert.match(html, /sem tributos e com o adicional de bandeira/)
      assert.match(html, /Os dois efeitos somam a variação da receita/)
      assert.match(html, /Sobre: Preço médio por kWh/)
    })

    await t.test('a ajuda de geração solar não transforma ausência de GD em dado disponível', () => {
      const html = renderToStaticMarkup(createElement(GeracaoSection, { dados: { cadastro: { possui_gd: false }, geracao_distribuida: null } }))
      assert.match(html, /Sem geração solar/)
      assert.match(html, /não é a energia gerada por mês/)
      assert.match(html, /Sobre: Geração solar/)
    })
  } finally {
    await server.close()
  }
})
