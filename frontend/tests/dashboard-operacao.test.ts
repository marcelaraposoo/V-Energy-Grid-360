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
import type { ConsumoLocaisResponse, OperacaoResponse } from '../src/api/types.ts'
import { parametrosDashboard } from '../src/features/dashboard/consultas.ts'
import { atendimentos, pontosNota, satisfacao } from '../src/features/dashboard/formatacao.ts'
import { linkQualidade, periodosQualidadeDaUrl } from '../src/features/qualidade/url.ts'
import { linkReceita } from '../src/features/receita/periodos.ts'

const periodo = { inicio: '2025-07', fim: '2026-06' }
const referencia = { inicio: '2022-07', fim: '2023-06' }
const operacao: OperacaoResponse = {
  periodo_atual: periodo, periodo_base: referencia, municipio: 'Recife',
  atual: { qtd_atendimentos: 35531, qtd_avaliacoes: 34485, nota_satisfacao_media: 3.9, dec_horas: 3.9, fec_vezes: 1.39, qtd_interrupcoes: 24958 },
  base: { qtd_atendimentos: 30810, qtd_avaliacoes: 29871, nota_satisfacao_media: 4.1, dec_horas: 1.48, fec_vezes: 0.9, qtd_interrupcoes: 16019 },
  variacao_atendimentos_pct: 15.32, variacao_satisfacao: -0.2, variacao_dec_pct: 163.51, variacao_fec_pct: 54.44,
}

test('formatadores de atendimento e satisfação', () => {
  assert.match(atendimentos(35531), /^35,5\smil$/)
  assert.equal(atendimentos(2318), '2.318')
  assert.equal(satisfacao(3.9), '3,9 de 5')
  assert.equal(pontosNota(-0.2), '−0,2 ponto')
  assert.equal(pontosNota(2.5), '+2,5 pontos')
})

test('o município segue para todas as consultas do Dashboard, inclusive operação', async () => {
  const urls: URL[] = []
  const api = createApi(createHttp('http://test', async (url) => {
    urls.push(new URL(String(url)))
    return new Response(JSON.stringify({}))
  }))
  const params = { ...parametrosDashboard(periodo, referencia), municipio: 'Recife' }
  await api.dashboard.kpis({ ...params, indicador: 'executivo' })
  await api.dashboard.serie(params)
  await api.dashboard.cadastroGd(params)
  await api.dashboard.consumoClasses(params)
  await api.dashboard.consumoLocais(params)
  assert.equal(urls.at(-1)?.pathname, '/api/dashboard/consumo-locais')
  await api.dashboard.operacao(params)
  assert.equal(urls.at(-1)?.pathname, '/api/dashboard/operacao')
  for (const url of urls) {
    assert.equal(url.searchParams.get('municipio'), 'Recife')
    assert.equal(url.searchParams.get('base_inicio'), '2022-07')
    assert.equal(url.searchParams.has('bairro'), false)
  }
})

test('links levam períodos e município para a Receita e a Qualidade', () => {
  assert.equal(linkReceita(periodo, referencia, 'Recife'),
    '/receita?atual_inicio=2025-07&atual_fim=2026-06&base_inicio=2022-07&base_fim=2023-06&municipio=Recife')
  assert.equal(linkReceita(periodo, null, 'Jaboatão dos Guararapes'), '/receita?municipio=Jaboat%C3%A3o+dos+Guararapes')
  assert.equal(linkReceita(periodo, null), '/receita')

  const comReferencia = linkQualidade(periodo, referencia, 'Recife')
  assert.equal(comReferencia, '/qualidade?atual_inicio=2025-07&atual_fim=2026-06&base_inicio=2022-07&base_fim=2023-06&municipio=Recife')
  assert.deepEqual(periodosQualidadeDaUrl(new URLSearchParams(comReferencia.split('?')[1])), { periodo, referencia })
  const semReferencia = linkQualidade({ inicio: '2024-07', fim: '2026-06' }, null)
  assert.deepEqual(periodosQualidadeDaUrl(new URLSearchParams(semReferencia.split('?')[1])),
    { periodo: { inicio: '2024-07', fim: '2026-06' }, referencia: null })
  // Inválidos ou incompletos: a Qualidade abre no padrão.
  for (const busca of ['', 'atual_inicio=2025-07', 'atual_inicio=2020-01&atual_fim=2020-06',
    'atual_inicio=2025-07&atual_fim=2026-06&base_inicio=2026-01&base_fim=2026-12', 'atual_inicio=2025-07&atual_fim=2026-06&base_inicio=2022-07']) {
    assert.equal(periodosQualidadeDaUrl(new URLSearchParams(busca)), null, busca)
  }
})

test('cards de operação e atendimento', async (t) => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { OperacaoCards } = await server.ssrLoadModule('/src/features/dashboard/OperacaoCards.tsx')
    const { InadimplenciaCard } = await server.ssrLoadModule('/src/features/dashboard/InadimplenciaCard.tsx')
    const estado = (data: unknown, extra = {}) => ({ data, loading: false, error: null, reload: () => {}, ...extra })
    const renderizar = (props: Record<string, unknown>) => renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(OperacaoCards, { estado: estado(operacao), referencia, municipio: 'Recife', linkQualidade: '/qualidade?municipio=Recife', ...props })))

    await t.test('com referência: valores, comparações e cores (subir é ruim, exceto a satisfação)', () => {
      const html = renderizar({})
      assert.match(html, /Operação e atendimento/)
      assert.match(html, /href="\/qualidade\?municipio=Recife"/)
      assert.match(html, /35,5\smil/)
      assert.match(html, /3,9 de 5/)
      assert.match(html, /Referência: 4,1 de 5/)
      assert.match(html, /data-tendencia="desfavoravel"[^>]*>.*?−0,2 ponto/)
      assert.match(html, /3,90 h/)
      assert.match(html, /Referência: 1,48 h/)
      assert.match(html, /1,39/)
      // Atendimentos, DEC e FEC subiram: os três aparecem como desfavoráveis.
      assert.equal((html.match(/data-tendencia="desfavoravel"/g) ?? []).length, 4)
      assert.doesNotMatch(html, /data-tendencia="favoravel"/)
      assert.match(html, /34\.485 de 35\.531 chamados tiveram nota/)
      assert.match(html, /município principal é Recife/)
    })

    await t.test('sem referência não mostra comparações; sem município, não fala de município principal', () => {
      const html = renderizar({ referencia: null, municipio: null, estado: estado({ ...operacao, base: null, periodo_base: null }) })
      assert.doesNotMatch(html, /Referência:|Sem dados para comparação|ponto/)
      assert.doesNotMatch(html, /município principal/)
    })

    await t.test('dados ausentes ficam como "—", sem inventar zero', () => {
      const vazio = { ...operacao, atual: { ...operacao.atual, nota_satisfacao_media: null, dec_horas: null, fec_vezes: null }, variacao_dec_pct: null }
      const html = renderizar({ estado: estado(vazio) })
      assert.equal((html.match(/kpi-card-valor"[^>]*>—</g) ?? []).length, 3)
      assert.match(html, /Sem dados para comparação/)
    })

    await t.test('carregando e erro não mostram valores antigos', () => {
      const carregando = renderizar({ estado: estado(operacao, { loading: true }) })
      assert.match(carregando, /Carregando operação e atendimento/)
      assert.doesNotMatch(carregando, /35,5/)
      const erro = renderizar({ estado: estado(operacao, { error: new Error('Falha') }) })
      assert.match(erro, /Tentar novamente/)
      assert.doesNotMatch(erro, /35,5/)
    })

    await t.test('faturamento em aberto: diferença que arredonda para 0,0 p.p. fica neutra', () => {
      const kpi = { nome: 'Inadimplência', unidade: '%', valor_atual: 5.58, valor_base: 5.61, variacao_abs: null, variacao_pct: null, variacao_pp: -0.03 }
      const html = renderToStaticMarkup(createElement(InadimplenciaCard, {
        periodo, referencia, estado: estado({ periodo_atual: periodo, periodo_base: referencia, kpis: [kpi] }),
      }))
      assert.match(html, /0,0 p\.p\./)
      assert.doesNotMatch(html, /data-tendencia="(favoravel|desfavoravel)"/)
    })
  } finally {
    await server.close()
    httpServer.close()
  }
})

const municipios = ['Recife', 'Jaboatão dos Guararapes', 'Olinda', 'Paulista', 'Cabo de Santo Agostinho', 'Camaragibe', 'Moreno']
const locais = (nivel: 'municipio' | 'bairro'): ConsumoLocaisResponse => ({
  periodo_atual: periodo, periodo_base: referencia, municipio: nivel === 'bairro' ? 'Recife' : null, nivel, consumo_total_kwh: 280,
  locais: municipios.map((nome, i) => ({
    municipio: nivel === 'bairro' ? 'Recife' : nome, bairro: nivel === 'bairro' ? `Bairro ${i + 1}` : null,
    consumo_kwh: 70 - i * 10, participacao_pct: 25 - i, consumo_referencia_kwh: 70, variacao_pct: i === 0 ? 0 : -i,
    competencias_ausentes: [],
  })),
})

test('energia por município ou bairro: lista curta no card e completa no modal', async (t) => {
  const httpServer = createHttpServer()
  const server = await createServer({
    configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null },
  })
  try {
    const { ClassesChart } = await server.ssrLoadModule('/src/features/dashboard/ClassesChart.tsx')
    const { ConsumoLocaisDialog } = await server.ssrLoadModule('/src/features/dashboard/ConsumoLocaisDialog.tsx')
    const estado = (data: unknown, extra = {}) => ({ data, loading: false, error: null, reload: () => {}, ...extra })
    const classes = estado({ periodo_atual: periodo, periodo_base: referencia, consumo_total_kwh: 0, classes: [] })
    const renderizar = (props: Record<string, unknown>) => renderToStaticMarkup(createElement(ClassesChart, {
      estado: classes, periodo, referencia, agrupamento: 'local', onAgrupamento: () => {}, onMunicipio: () => {}, ...props,
    }))

    await t.test('município: cinco linhas (a altura das classes), clicáveis, e "Mostrar todos"', () => {
      const html = renderizar({ locais: estado(locais('municipio')) })
      assert.match(html, /Energia faturada por município/)
      assert.match(html, /aria-pressed="true"[^>]*>Município</)
      assert.equal((html.match(/class="dashboard-class-row"/g) ?? []).length, 5)
      assert.match(html, /Cabo de Santo Agostinho/)
      assert.doesNotMatch(html, /Camaragibe|Moreno/)
      assert.match(html, /5 de 7 municípios · Variação vs\. referência/)
      assert.match(html, /Mostrar todos/)
      assert.match(html, /Filtrar o Dashboard por este município/)
    })

    await t.test('bairro: título com o município e linhas que não filtram', () => {
      const html = renderizar({ municipio: 'Recife', locais: estado(locais('bairro')) })
      assert.match(html, /Energia faturada por bairro/)
      assert.match(html, /Recife · Jul\/2025–Jun\/2026/)
      assert.match(html, />Bairro</)
      assert.equal((html.match(/dashboard-class-row--estatica/g) ?? []).length, 5)
      assert.doesNotMatch(html, /Filtrar o Dashboard/)
      assert.match(html, /5 de 7 bairros/)
    })

    await t.test('até cinco locais: sem "Mostrar todos"; carregando e erro sem dados antigos', () => {
      const poucos = { ...locais('municipio'), locais: locais('municipio').locais.slice(0, 3) }
      const html = renderizar({ locais: estado(poucos), referencia: null })
      assert.match(html, /3 municípios · Participação no consumo do período/)
      assert.doesNotMatch(html, /Mostrar todos|dashboard-class-change/)
      assert.match(renderizar({ locais: estado(null, { loading: true }) }), /Carregando consumo por município/)
      assert.match(renderizar({ locais: estado(null, { error: new Error('Falha') }) }), /Tentar novamente/)
    })

    await t.test('classe continua sendo o padrão, com a troca disponível', () => {
      const html = renderizar({ agrupamento: 'classe', locais: estado(null) })
      assert.match(html, /Energia faturada por classe/)
      assert.match(html, /aria-pressed="true"[^>]*>Classe</)
    })

    await t.test('modal lista todos os locais, com a referência de cada um', () => {
      const html = renderToStaticMarkup(createElement(ConsumoLocaisDialog, {
        aberto: true, dados: locais('municipio'), periodo, referencia, onFechar: () => {}, onMunicipio: () => {},
      }))
      for (const nome of municipios) assert.match(html, new RegExp(nome))
      assert.equal((html.match(/Referência: 70 kWh/g) ?? []).length, municipios.length)
      assert.match(html, /7 municípios, do maior para o menor consumo\. Selecione um município/)
    })
  } finally {
    await server.close()
    httpServer.close()
  }
})
