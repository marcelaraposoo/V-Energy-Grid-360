import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import type { DashboardParams, Periodo } from '../src/api/types.ts'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'
import { alterarPeriodos, estadoInicial } from '../src/features/dashboard/periodos.ts'
import { limitesDashboard, quantidadeMeses, referenciaAutomatica, sugerirReferencia, validarPeriodosDashboard } from '../src/utils/periodosDashboard.ts'

const casos = JSON.parse(readFileSync(new URL('../../backend/tests/fixtures/dashboard_periodos.json', import.meta.url), 'utf8')) as {
  nome: string; atual: Periodo; base: Periodo | null; valido: boolean
}[]
for (const caso of casos) {
  test(caso.nome, () => assert.equal(!validarPeriodosDashboard(caso.atual, caso.base, caso.base !== null), caso.valido))
}

test('duração mensal inclusiva, inclusive em fevereiro bissexto', () => {
  assert.equal(quantidadeMeses({ inicio: '2024-02', fim: '2024-02' }), 1)
  assert.equal(quantidadeMeses({ inicio: '2024-12', fim: '2025-03' }), 4)
})

test('sugestão: ano anterior ou bloco anterior; período posterior exige escolha personalizada', () => {
  assert.deepEqual(sugerirReferencia({ inicio: '2026-05', fim: '2026-05' }), { inicio: '2025-05', fim: '2025-05' })
  assert.deepEqual(sugerirReferencia({ inicio: '2023-01', fim: '2023-03' }), { inicio: '2022-10', fim: '2022-12' })
  assert.equal(sugerirReferencia({ inicio: '2022-07', fim: '2022-09' }), null)
})

const padrao = { inicio: '2025-07', fim: '2026-06' }
const reduzir = (e: ReturnType<typeof estadoInicial>, a: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(e, a, padrao, limitesDashboard)

test('estado inicial e limpar mantêm o período principal sem referência', () => {
  const estado = estadoInicial(padrao)
  assert.deepEqual(estado.periodo, padrao)
  assert.equal(estado.comparar, false)
  assert.equal(estado.referencia, null)
  assert.equal(estado.aviso, null)
  const comReferencia = reduzir(estado, { tipo: 'referencia', valor: { inicio: '2022-07', fim: '2023-06' } })
  assert.equal(comReferencia.comparar, true)
  assert.deepEqual(reduzir(comReferencia, { tipo: 'limpar' }), estado)
  const alterado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2026-05', fim: '2026-05' } })
  assert.equal(alterado.comparar, false)
  assert.equal(alterado.referencia, null)
})

test('padrão do Dashboard abre comparando com o primeiro ano da base; limpar volta a ele', () => {
  const primeiroAno = { inicio: '2022-07', fim: '2023-06' }
  const reduzirComBase = (e: ReturnType<typeof estadoInicial>, a: Parameters<typeof alterarPeriodos>[1]) =>
    alterarPeriodos(e, a, padrao, limitesDashboard, primeiroAno)
  const inicial = estadoInicial(padrao, primeiroAno)
  assert.equal(inicial.comparar, true)
  assert.deepEqual(inicial.referencia, primeiroAno)
  assert.equal(validarPeriodosDashboard(inicial.periodo, inicial.referencia, true), null)
  // Período de outra duração troca a referência pela sugestão automática.
  const curto = reduzirComBase(inicial, { tipo: 'periodo', valor: { inicio: '2026-05', fim: '2026-05' } })
  assert.deepEqual(curto.referencia, { inicio: '2025-05', fim: '2025-05' })
  const semComparacao = reduzirComBase(curto, { tipo: 'comparar', valor: false })
  assert.deepEqual(reduzirComBase(semComparacao, { tipo: 'limpar' }), inicial)
})

test('alternância rápida sempre remove ou restaura uma referência válida', () => {
  let estado = estadoInicial(padrao)
  for (let i = 0; i < 50; i++) {
    estado = reduzir(estado, { tipo: 'comparar', valor: false })
    assert.equal(estado.referencia, null)
    estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2026-05', fim: '2026-05' } })
    estado = reduzir(estado, { tipo: 'comparar', valor: true })
    assert.deepEqual(estado.referencia, { inicio: '2025-05', fim: '2025-05' })
    assert.equal(validarPeriodosDashboard(estado.periodo, estado.referencia, estado.comparar), null)
  }
})

test('referência incompatível é ajustada; seleção atrasada não sobrescreve o estado válido', () => {
  let estado = reduzir(estadoInicial(padrao), { tipo: 'comparar', valor: true })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2026-05', fim: '2026-05' } })
  estado = reduzir(estado, { tipo: 'referencia', valor: padrao })
  assert.deepEqual(estado.referencia, { inicio: '2025-05', fim: '2025-05' })
  estado = reduzir(estado, { tipo: 'comparar', valor: false })
  estado = reduzir(estado, { tipo: 'referencia', valor: padrao })
  assert.equal(estado.referencia, null)
  estado = reduzir(estado, { tipo: 'referencia', valor: { inicio: '2025-05', fim: '2025-05' } })
  assert.equal(estado.comparar, true)
  assert.deepEqual(estado.referencia, { inicio: '2025-05', fim: '2025-05' })
})

test('24 meses continuam sem comparação ao tentar ativar; limpar restaura o padrão', () => {
  let estado = reduzir(estadoInicial(padrao), { tipo: 'comparar', valor: false })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2024-07', fim: '2026-06' } })
  estado = reduzir(estado, { tipo: 'comparar', valor: true })
  assert.equal(estado.comparar, false)
  assert.equal(estado.referencia, null)
  assert.match(estado.aviso!, /12 meses/)
  assert.deepEqual(reduzir(estado, { tipo: 'limpar' }), estadoInicial(padrao))
})

test('base curta sem referência informa o motivo e permite desativar', () => {
  const limites = { minimo: '2025-01', maximo: '2025-12' }
  const atual = { inicio: '2025-01', fim: '2025-08' }
  const inicial = estadoInicial(atual)
  assert.equal(inicial.aviso, null)
  const estado = alterarPeriodos(inicial, { tipo: 'comparar', valor: true }, atual, limites)
  assert.equal(estado.referencia, null)
  assert.equal(estado.comparar, false)
  assert.match(estado.aviso!, /sugestão/)
  const desligado = alterarPeriodos(estado, { tipo: 'comparar', valor: false }, atual, limites)
  assert.equal(validarPeriodosDashboard(desligado.periodo, desligado.referencia, false, limites), null)
})

test('opções automáticas têm a mesma duração e acompanham mudanças no principal', () => {
  const principal = { inicio: '2026-01', fim: '2026-06' }
  assert.deepEqual(referenciaAutomatica(principal, 'ano_anterior'), { inicio: '2025-01', fim: '2025-06' })
  assert.deepEqual(referenciaAutomatica(principal, 'periodo_anterior'), { inicio: '2025-07', fim: '2025-12' })
  let estado = reduzir(estadoInicial(padrao), { tipo: 'periodo', valor: principal })
  estado = reduzir(estado, { tipo: 'modo', valor: 'periodo_anterior' })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2026-02', fim: '2026-07' } })
  assert.deepEqual(estado.periodo, principal) // Julho/2026 está fora da base.
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2025-12', fim: '2026-05' } })
  assert.deepEqual(estado.referencia, { inicio: '2025-06', fim: '2025-11' })
  assert.equal(estado.modoReferencia, 'periodo_anterior')
})

test('referência manual válida é preservada mesmo quando coincide com uma opção automática', () => {
  let estado = reduzir(estadoInicial(padrao), { tipo: 'periodo', valor: { inicio: '2026-01', fim: '2026-04' } })
  estado = reduzir(estado, { tipo: 'referencia', valor: { inicio: '2025-01', fim: '2025-04' } })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2026-02', fim: '2026-05' } })
  assert.deepEqual(estado.referencia, { inicio: '2025-01', fim: '2025-04' })
  assert.equal(estado.modoReferencia, 'personalizado')
  estado = reduzir(estado, { tipo: 'referencia', valor: { inicio: '2025-06', fim: '2025-09' } })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2025-01', fim: '2025-04' } })
  assert.deepEqual(estado.referencia, { inicio: '2025-06', fim: '2025-09' })
})

test('automática indisponível informa o motivo e permite referência personalizada posterior', () => {
  let estado = reduzir(estadoInicial(padrao), { tipo: 'comparar', valor: false })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2022-07', fim: '2022-09' } })
  estado = reduzir(estado, { tipo: 'modo', valor: 'ano_anterior' })
  assert.equal(estado.comparar, false)
  assert.equal(estado.referencia, null)
  assert.match(estado.aviso!, /competências disponíveis/)
  estado = reduzir(estado, { tipo: 'referencia', valor: { inicio: '2022-10', fim: '2022-12' } })
  assert.equal(estado.comparar, true)
  assert.equal(estado.modoReferencia, 'personalizado')
})

test('opção automática que fica inválida não mantém uma referência antiga sem aviso', () => {
  let estado = reduzir(estadoInicial(padrao), { tipo: 'modo', valor: 'ano_anterior' })
  estado = reduzir(estado, { tipo: 'periodo', valor: { inicio: '2022-07', fim: '2023-06' } })
  assert.equal(estado.comparar, false)
  assert.equal(estado.referencia, null)
  assert.match(estado.aviso!, /indisponível/)
})

test('cliente omite base_* sem comparação, mantém filtros e repassa o cancelamento', async () => {
  let url = ''
  let signal: AbortSignal | null | undefined
  const fetchFake: typeof fetch = async (input, init) => {
    url = String(input); signal = init?.signal
    return new Response(JSON.stringify({ kpis: [] }), { status: 200 })
  }
  const api = createApi(createHttp('http://test', fetchFake))
  const controle = new AbortController()
  await api.dashboard.kpis({ comparar: false, atual_inicio: '2026-05', atual_fim: '2026-05',
    base_inicio: '2025-05', base_fim: '2025-05', municipio: 'Recife', bairro: 'Centro', classe: 'RESIDENCIAL',
  } as unknown as DashboardParams, controle.signal)
  const params = new URL(url).searchParams
  assert.equal(params.get('comparar'), 'false')
  assert.equal(params.has('base_inicio'), false)
  assert.equal(params.has('base_fim'), false)
  assert.equal(params.get('municipio'), 'Recife')
  assert.equal(params.get('bairro'), 'Centro')
  assert.equal(params.get('classe'), 'RESIDENCIAL')
  assert.equal(signal, controle.signal)
})

test('requisições inválidas são barradas antes do fetch, para KPIs e série', () => {
  let chamadas = 0
  const api = createApi(createHttp('http://test', async () => { chamadas++; return new Response('[]') }))
  for (const metodo of [api.dashboard.kpis, api.dashboard.serie]) {
    assert.throws(() => metodo({ atual_inicio: '2026-01', atual_fim: '2026-06', base_inicio: '2026-03', base_fim: '2026-06' }))
    assert.throws(() => metodo({ atual_inicio: '2026-01' }))
    assert.throws(() => metodo({ comparar: false, atual_inicio: '2022-07', atual_fim: '2026-06' }))
  }
  assert.equal(chamadas, 0)
})

test('cliente mantém o padrão sem parâmetros e envia sugestão válida ao receber período explícito', async () => {
  const urls: string[] = []
  const api = createApi(createHttp('http://test', async (url) => { urls.push(String(url)); return new Response('[]') }))
  await api.dashboard.kpis()
  assert.equal(new URL(urls[0]).search, '')
  await api.dashboard.kpis({ atual_inicio: '2026-05', atual_fim: '2026-05' })
  assert.equal(new URL(urls[1]).searchParams.get('base_inicio'), '2025-05')
  await api.dashboard.serie({ comparar: false, atual_inicio: '2026-05', atual_fim: '2026-05' })
  assert.equal(new URL(urls[2]).searchParams.has('base_inicio'), false)
})
