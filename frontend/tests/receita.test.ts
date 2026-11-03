import assert from 'node:assert/strict'
import test from 'node:test'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'
import { alterarRecorte, aprofundar, filtrar, recorteInicial } from '../src/features/receita/drilldown.ts'
import type { HistoricoRecortes } from '../src/features/receita/drilldown.ts'
import { linkReceita, periodosDaUrl, periodosDiagnostico } from '../src/features/receita/periodos.ts'
import { parametrosReceita } from '../src/features/receita/tipos.ts'
import type { LinhaReceita } from '../src/features/receita/tipos.ts'

function linha(campos: Partial<LinhaReceita>): LinhaReceita {
  return {
    chave: 'x', rotulo: 'x', municipio: null, bairro: null, classe: null,
    receita_base: 100, receita_atual: 110, variacao_receita: 10, variacao_receita_pct: 10,
    efeito_preco: 15, efeito_volume: -5, energia_base_kwh: 200, energia_atual_kwh: 190, variacao_energia_pct: -5,
    preco_base_kwh: 0.5, preco_atual_kwh: 0.58, qtd_ucs_base: 10, qtd_ucs_atual: 10, ...campos,
  }
}

test('voltar restaura filtros e agrupamento em cada nível do detalhamento', () => {
  let estado: HistoricoRecortes = { atual: recorteInicial, anteriores: [] }
  const residencial = filtrar(recorteInicial, { classe: 'RESIDENCIAL' })
  const municipio = filtrar(residencial, { municipio: 'Recife' })
  const bairro = filtrar(municipio, { bairro: 'Madalena' })
  for (const valor of [residencial, municipio, bairro]) estado = alterarRecorte(estado, { tipo: 'selecionar', valor })
  for (const esperado of [municipio, residencial, recorteInicial]) {
    estado = alterarRecorte(estado, { tipo: 'voltar' })
    assert.deepEqual(estado.atual, esperado)
  }
  assert.deepEqual(estado.anteriores, [])
  assert.equal(alterarRecorte(estado, { tipo: 'voltar' }), estado)
})

test('histórico ignora a mesma seleção, registra troca de agrupamento e limpa com os filtros', () => {
  const inicial: HistoricoRecortes = { atual: recorteInicial, anteriores: [] }
  assert.equal(alterarRecorte(inicial, { tipo: 'selecionar', valor: { ...recorteInicial } }), inicial)
  const porClasse = alterarRecorte(inicial, { tipo: 'selecionar', valor: { ...recorteInicial, agrupar_por: 'classe' } })
  assert.equal(alterarRecorte(porClasse, { tipo: 'voltar' }).atual.agrupar_por, 'municipio')
  assert.deepEqual(alterarRecorte(porClasse, { tipo: 'limpar' }), inicial)
})

test('drill-down: município → bairro → classe; voltar limpa os níveis abaixo', () => {
  const municipio = filtrar(recorteInicial, { municipio: 'Recife' })
  assert.deepEqual(municipio, { municipio: 'Recife', bairro: null, classe: null, agrupar_por: 'bairro' })
  const bairro = filtrar(municipio, { bairro: 'Madalena' })
  assert.equal(bairro.agrupar_por, 'classe')
  assert.deepEqual(filtrar(bairro, { municipio: null }), recorteInicial)
  // Trocar de município nunca carrega o bairro do anterior (bairro só existe junto com o município).
  assert.equal(filtrar(bairro, { municipio: 'Olinda' }).bairro, null)
})

test('drill-down: classe preserva o agrupamento e não pode ser agrupamento quando filtrada', () => {
  const porMunicipio = filtrar(recorteInicial, { classe: 'RESIDENCIAL' })
  assert.equal(porMunicipio.agrupar_por, 'municipio')
  const porClasse = filtrar({ ...recorteInicial, agrupar_por: 'classe' }, { classe: 'COMERCIAL' })
  assert.equal(porClasse.agrupar_por, 'municipio')
})

test('drill-down: clicar na linha desce um nível e para no bairro agrupado por classe', () => {
  const destino = aprofundar(recorteInicial, linha({ chave: 'Recife', rotulo: 'Recife', municipio: 'Recife' }))
  assert.deepEqual(destino, { municipio: 'Recife', bairro: null, classe: null, agrupar_por: 'bairro' })
  const noBairro = aprofundar(destino!, linha({ chave: 'Madalena - Recife', rotulo: 'Madalena', municipio: 'Recife', bairro: 'Madalena' }))
  assert.deepEqual(noBairro, { municipio: 'Recife', bairro: 'Madalena', classe: null, agrupar_por: 'classe' })
  assert.equal(aprofundar(noBairro!, linha({ chave: 'RESIDENCIAL', classe: 'RESIDENCIAL' })), null)
  // Sem território, a classe filtra e volta ao nível de município.
  const porClasse = aprofundar({ ...recorteInicial, agrupar_por: 'classe' }, linha({ chave: 'COMERCIAL', classe: 'COMERCIAL' }))
  assert.deepEqual(porClasse, { municipio: null, bairro: null, classe: 'COMERCIAL', agrupar_por: 'municipio' })
})

test('consulta envia períodos, filtros e agrupamento; filtros vazios não saem do cliente', async () => {
  const urls: string[] = []
  const api = createApi(createHttp('http://test', async (url) => { urls.push(String(url)); return new Response('{}') }))
  await api.receita.variacao(parametrosReceita({ ...recorteInicial, ...periodosDiagnostico }))
  await api.receita.variacao(parametrosReceita({
    municipio: 'Jaboatão dos Guararapes', bairro: 'Piedade', classe: 'PODER PUBLICO', agrupar_por: 'classe',
    periodo: { inicio: '2026-01', fim: '2026-06' }, referencia: { inicio: '2025-01', fim: '2025-06' },
  }))
  const [padrao, filtrada] = urls.map((url) => Object.fromEntries(new URL(url).searchParams))
  assert.deepEqual(padrao, {
    base_inicio: '2022-07', base_fim: '2023-06', atual_inicio: '2025-07', atual_fim: '2026-06', agrupar_por: 'municipio',
  })
  assert.deepEqual(filtrada, {
    base_inicio: '2025-01', base_fim: '2025-06', atual_inicio: '2026-01', atual_fim: '2026-06',
    municipio: 'Jaboatão dos Guararapes', bairro: 'Piedade', classe: 'PODER PUBLICO', agrupar_por: 'classe',
  })
})

test('link do Dashboard leva os mesmos períodos; a Receita só aceita períodos válidos', () => {
  const periodo = { inicio: '2026-01', fim: '2026-06' }
  const referencia = { inicio: '2025-01', fim: '2025-06' }
  const link = linkReceita(periodo, referencia)
  assert.equal(link, '/receita?atual_inicio=2026-01&atual_fim=2026-06&base_inicio=2025-01&base_fim=2025-06')
  assert.deepEqual(periodosDaUrl(new URLSearchParams(link.split('?')[1])), { periodo, referencia })
  // Sem referência no Dashboard, a Receita abre no recorte do diagnóstico.
  assert.equal(linkReceita(periodo, null), '/receita')
  assert.equal(periodosDaUrl(new URLSearchParams('')), null)
  // Sobreposição, durações diferentes ou fora da base: ignora a URL.
  for (const busca of [
    'atual_inicio=2026-01&atual_fim=2026-06&base_inicio=2025-12&base_fim=2026-05',
    'atual_inicio=2026-01&atual_fim=2026-06&base_inicio=2025-01&base_fim=2025-03',
    'atual_inicio=2026-02&atual_fim=2026-07&base_inicio=2025-02&base_fim=2025-07',
  ]) assert.equal(periodosDaUrl(new URLSearchParams(busca)), null)
})
