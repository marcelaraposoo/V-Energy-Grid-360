import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'
import { competenciasInsights } from '../src/features/unidades/insights.ts'

test('insights da UC comparam o último mês com o mesmo mês do ano anterior', () => {
  assert.deepEqual(competenciasInsights(['2025-05', '2025-06', '2026-05', '2026-06']), {
    params: { competencia_atual: '2026-06', competencia_referencia: '2025-06' }, descricao: '06/2026 comparado a 06/2025 e aos 6 meses anteriores',
  })
  // Sem o mesmo mês do ano anterior, o backend usa o mês anterior.
  assert.deepEqual(competenciasInsights(['2026-05', '2026-06']), {
    params: { competencia_atual: '2026-06' }, descricao: '06/2026 comparado ao mês anterior e aos 6 meses anteriores',
  })
  assert.deepEqual(competenciasInsights([]).params, {})
})

test('rota dos insights da UC leva as competências escolhidas', async () => {
  const urls: URL[] = []
  const api = createApi(createHttp('http://test', async (url) => {
    urls.push(new URL(String(url)))
    return new Response('[]')
  }))
  await api.ia.insightsUc('UC 108564', { competencia_atual: '2026-06', competencia_referencia: '2025-06' })
  assert.equal(urls[0].pathname, '/api/ia/insights/uc/UC%20108564')
  assert.equal(urls[0].searchParams.get('competencia_referencia'), '2025-06')
})

test('card de insights da UC: carregando antes da resposta', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { InsightsUcCard } = await server.ssrLoadModule('/src/features/unidades/components/InsightsUcCard.tsx')
    const html = renderToStaticMarkup(createElement(InsightsUcCard, { ucId: 'UC108564', competencias: ['2025-06', '2026-06'] }))
    assert.match(html, /class="panel-title-icone"><svg[^>]*lucide-sparkles/)
    assert.match(html, /Insights da IA/)
    assert.match(html, /06\/2026 comparado a 06\/2025 e aos 6 meses anteriores/)
    assert.match(html, /Gerando insights/)
    assert.doesNotMatch(html, /A conta veio alta/)
  } finally {
    await server.close()
    httpServer.close()
  }
})

const fatura = {
  uc_id: 'UC108564', competencia: '2026-06', municipio: 'Jaboatão dos Guararapes', bairro: 'Socorro', classe: 'RESIDENCIAL',
  alimentador_id: 'ALM-JAB-016', consumo_kwh: 77, valor: 46.6, bandeira: 'Vermelha P2', vencimento: '2026-06-25',
  status: 'atrasada', faixa_atraso: 'MAIS DE 90 DIAS', id_fatura: 'F1', data_pagamento: null,
  valor_energia: 46.6, valor_total: 62.13, tributos: 15.53, preco_medio_kwh: 0.6052,
}

test('modal da fatura: total em destaque, bandeira, composição e detalhes', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { FaturaDialog } = await server.ssrLoadModule('/src/features/unidades/components/FaturaDialog.tsx')
    const { BandeiraTarifaria } = await server.ssrLoadModule('/src/features/unidades/components/BandeiraTarifaria.tsx')
    const html = renderToStaticMarkup(createElement(FaturaDialog, { fatura, onFechar: () => {} }))
    assert.match(html, /Fatura de 06\/2026/)
    assert.match(html, /Mais de 90 dias de atraso/)
    assert.match(html, /R\$\s62,13/)
    assert.match(html, /data-tom="vermelha-p2"/)
    assert.match(html, /aria-label="Energia: 75% do total; tributos: 25%\."/)
    assert.match(html, /Preço médio por kWh/)
    assert.match(html, /Em aberto/)
    // Sem energia ou tributos, a barra de composição não aparece.
    const semTributos = renderToStaticMarkup(createElement(FaturaDialog, { fatura: { ...fatura, tributos: null }, onFechar: () => {} }))
    assert.doesNotMatch(semTributos, /ucv-fatura-dialog-barra/)
    assert.match(renderToStaticMarkup(createElement(BandeiraTarifaria, { bandeira: 'Verde' })), /data-tom="verde"/)
    assert.match(renderToStaticMarkup(createElement(BandeiraTarifaria, { bandeira: null })), /Não informada/)
  } finally {
    await server.close()
    httpServer.close()
  }
})
