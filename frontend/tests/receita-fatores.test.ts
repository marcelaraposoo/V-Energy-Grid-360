import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

test('fatores associados mostram comparações e preservam indisponibilidade', async (t) => {
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: createHttpServer() }, watch: null },
  })
  try {
    const { FatoresReceita } = await server.ssrLoadModule('/src/features/receita/FatoresReceita.tsx')
    const fatores = {
      qtd_ucs_com_gd: 3, energia_ucs_gd_base_kwh: 600, energia_ucs_gd_atual_kwh: 400,
      qtd_trocas_medidor_atual: 12, pct_faturas_bandeira_nao_verde_base: 0, pct_faturas_bandeira_nao_verde_atual: 66.7,
    }
    const total = { energia_base_kwh: 1000, energia_atual_kwh: 900, preco_base_kwh: 0.5 }
    const renderizar = (mudancas = {}, totais = {}) => renderToStaticMarkup(createElement(FatoresReceita, {
      analise: { fatores: { ...fatores, ...mudancas }, total: { ...total, ...totais } },
    }))

    await t.test('inicia em GD e mantém bandeira e medidores juntos em uma segunda página inacessível até navegar', () => {
      const html = renderizar()
      assert.match(html, /aria-labelledby="fator-gd-titulo"[^>]*aria-hidden="false"/)
      assert.match(html, /class="receita-fatores-pagina-dupla"[^>]*aria-hidden="true"[^>]*inert=""/)
      assert.match(html, /Próximo fator: Bandeira tarifária e trocas de medidor/)
      assert.match(html, /role="status"[^>]*>1 de 2/)
    })

    await t.test('GD compara as mesmas UCs e descreve o crescimento das demais sem hipótese causal', () => {
      const html = renderizar()
      assert.match(html, /Consumo das mesmas UCs/)
      assert.match(html, /−33,3%/)
      assert.match(html, /Demais UCs<\/span><strong>\+25,0%/)
      assert.match(html, /−R\$ 100,0/)
      assert.doesNotMatch(html, /teria crescido|NaN|Infinity/)
    })

    await t.test('a mudança de bandeira aparece em pontos percentuais', () => {
      assert.match(renderizar(), /\+66,7 p\.p\./)
      assert.match(renderizar({ pct_faturas_bandeira_nao_verde_base: 80, pct_faturas_bandeira_nao_verde_atual: 20 }), /−60,0 p\.p\./)
    })

    await t.test('sem volumes, preserva a contagem de GD e não inventa barras ou estimativa', () => {
      const html = renderizar({ energia_ucs_gd_base_kwh: null, energia_ucs_gd_atual_kwh: null })
      assert.match(html, /<strong>3<\/strong> UCs com geração solar/)
      assert.match(html, /Consumo dessas unidades indisponível/)
      assert.doesNotMatch(html, /class="receita-fator-comparacao"|class="receita-fator-impacto"/)
    })

    await t.test('preço ausente e referência zero não viram uma estimativa monetária de zero', () => {
      const html = renderizar({ energia_ucs_gd_base_kwh: 0 }, { preco_base_kwh: null })
      assert.match(html, /Indisponível/)
      assert.doesNotMatch(html, /≈ |NaN|Infinity/)
    })

    await t.test('zero e indisponível são apresentados de formas distintas', () => {
      const semGd = renderizar({ qtd_ucs_com_gd: 0, energia_ucs_gd_base_kwh: 0, energia_ucs_gd_atual_kwh: 0 })
      assert.match(semGd, /Nenhuma unidade com geração solar neste recorte/)
      const semBandeira = renderizar({ pct_faturas_bandeira_nao_verde_base: null, pct_faturas_bandeira_nao_verde_atual: null })
      assert.doesNotMatch(semBandeira, /p\.p\.|NaN|Infinity/)
      assert.match(semBandeira, /Indisponível/)
      assert.match(renderizar({ qtd_trocas_medidor_atual: 0 }), /<strong>0<\/strong><span>trocas no período analisado/)
    })
  } finally {
    await server.close()
  }
})
