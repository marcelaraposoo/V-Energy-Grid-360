import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

const alimentador = (id: string, dec: number, ucs: number, extra: Record<string, unknown> = {}) => ({
  alimentador_id: id, municipio: 'Recife', dec_horas: dec, fec_vezes: dec / 2, n_ocorrencias: 10,
  horas_interrompidas: dec * ucs, qtd_ucs_alimentador_mes: ucs, competencia_base_ucs: '2026-06',
  horas_causas_evitaveis: dec * ucs * 0.25, qtd_ucs_afetadas: Math.min(ucs, 10), posicao_pior: 1, ...extra,
})

test('qualidade do serviço: indicadores, causas e ranking dos alimentadores', async (t) => {
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: createHttpServer() }, watch: null },
  })
  try {
    const formatacao = await server.ssrLoadModule('/src/features/qualidade/formatacao.ts')
    const { KpisQualidade } = await server.ssrLoadModule('/src/features/qualidade/KpisQualidade.tsx')
    const { CausasQualidade } = await server.ssrLoadModule('/src/features/qualidade/CausasQualidade.tsx')
    const { RankingAlimentadores } = await server.ssrLoadModule('/src/features/qualidade/RankingAlimentadores.tsx')
    const { EvolucaoQualidade } = await server.ssrLoadModule('/src/features/qualidade/EvolucaoQualidade.tsx')

    await t.test('formatação e variação tratam ausência de referência', () => {
      assert.equal(formatacao.horas(3.451909), '3,45 h')
      assert.match(formatacao.horasImpacto(155221.04), /^155,2\smil h$/)
      assert.equal(formatacao.horasImpacto(878), '878 h')
      assert.equal(formatacao.variacaoPct(3, 1.5), 100)
      assert.equal(formatacao.variacaoPct(3, 0), null)
      assert.equal(formatacao.variacaoPct(null, 1), null)
      assert.equal(formatacao.nomeCausa(null), 'Não informada')
      assert.equal(formatacao.nomeCausa('FALHA DE EQUIPAMENTO'), 'Falha de equipamento')
    })

    await t.test('nos cards de DEC e FEC, subir é desfavorável', () => {
      const atual = { dec_horas: 3, fec_vezes: 1.2, qtd_interrupcoes: 100, horas_interrompidas: 500, horas_causas_evitaveis: 100, qtd_ucs: 10, competencia_base_ucs: '2026-06' }
      const base = { ...atual, dec_horas: 1.5, fec_vezes: 1.2, qtd_interrupcoes: 120 }
      const html = renderToStaticMarkup(createElement(KpisQualidade, { atual, base, referencia: { inicio: '2022-07', fim: '2023-06' } }))
      assert.match(html, /data-tendencia="desfavoravel"[^>]*>.*?\+100,0%/)
      assert.match(html, /data-tendencia="favoravel"[^>]*>.*?−16,7%/)
      assert.match(html, /Referência: 1,50 h/)
      assert.match(html, /Não é o número de consumidores afetados/)
      const semReferencia = renderToStaticMarkup(createElement(KpisQualidade, { atual: null, base: null, referencia: null }))
      assert.equal((semReferencia.match(/class="kpi-card-valor"[^>]*>—</g) ?? []).length, 4)
      assert.doesNotMatch(semReferencia, /Referência:/)
    })

    await t.test('causas destacam as evitáveis e a causa não informada', () => {
      const html = renderToStaticMarkup(createElement(CausasQualidade, { causas: [
        { causa: 'CLIMATICA', causa_evitavel: false, qtd_interrupcoes: 10, horas: 60, pct_horas: 60 },
        { causa: 'VEGETACAO', causa_evitavel: true, qtd_interrupcoes: 5, horas: 30, pct_horas: 30 },
        { causa: null, causa_evitavel: false, qtd_interrupcoes: 2, horas: 10, pct_horas: 10 },
      ] }))
      assert.match(html, /<strong>30,0%<\/strong> das horas sem energia vieram de causas evitáveis/)
      assert.equal((html.match(/qualidade-evitavel/g) ?? []).length, 1)
      assert.match(html, /Não informada/)
      assert.match(html, /width:50%/)
      assert.match(renderToStaticMarkup(createElement(CausasQualidade, { causas: [] })), /Nenhuma interrupção/)
    })

    await t.test('ranking começa pelo pior DEC e avisa sobre bases pequenas', () => {
      const alimentadores = [alimentador('ALM-B', 5, 2000), alimentador('ALM-A', 40, 20), alimentador('ALM-C', 1, 900)]
      const html = renderToStaticMarkup(createElement(RankingAlimentadores, {
        alimentadores, base: [alimentador('ALM-A', 20, 20)], referencia: { inicio: '2022-07', fim: '2023-06' },
        selecionado: 'ALM-B', onSelecionar: () => {},
      }))
      const ordem = [...html.matchAll(/<span>(ALM-[ABC])<small>/g)].map((m) => m[1])
      assert.deepEqual(ordem, ['ALM-A', 'ALM-B', 'ALM-C'])
      assert.match(html, /<strong>1 dos 3<\/strong> primeiros por DEC têm menos de 50 UCs/)
      assert.equal((html.match(/base pequena<\/span>/g) ?? []).length, 1)
      assert.match(html, /aria-sort="descending"><button[^>]*>DEC/)
      assert.match(html, /DEC na referência/)
      assert.match(html, />20,00 h</)
      assert.match(html, /200 h<small>\(25,0%\)<\/small>/)
      assert.match(html, /data-ativo="true"/)
      const semReferencia = renderToStaticMarkup(createElement(RankingAlimentadores, {
        alimentadores: [alimentador('ALM-C', 1, 900)], base: null, referencia: null, selecionado: null, onSelecionar: () => {},
      }))
      assert.doesNotMatch(semReferencia, /DEC na referência/)
      assert.doesNotMatch(semReferencia, /qualidade-aviso/)
    })

    await t.test('evolução exige todos os meses do período', () => {
      const periodo = { inicio: '2026-05', fim: '2026-06' }
      const ponto = (competencia: string) => ({ competencia, dec_horas: 0.2, fec_vezes: 0.1, qtd_interrupcoes: 5, horas_interrompidas: 10 })
      const completo = renderToStaticMarkup(createElement(EvolucaoQualidade, {
        serie: [ponto('2026-05'), ponto('2026-06')], serieBase: [], periodo, referencia: null, escopo: 'Distribuidora',
      }))
      assert.match(completo, /dashboard-chart/)
      assert.match(completo, /Distribuidora · horas por UC/)
      const incompleto = renderToStaticMarkup(createElement(EvolucaoQualidade, {
        serie: [ponto('2026-06')], serieBase: [], periodo, referencia: null, escopo: 'Distribuidora',
      }))
      assert.match(incompleto, /Sem dados para o período/)
    })
  } finally {
    await server.close()
  }
})
