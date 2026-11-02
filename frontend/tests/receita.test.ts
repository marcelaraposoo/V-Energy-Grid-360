import assert from 'node:assert/strict'
import test from 'node:test'
import { decompor } from '../src/features/receita/decomposicao.ts'
import { aprofundar, filtrar, recorteInicial } from '../src/features/receita/drilldown.ts'
import { analiseReceitaMock } from '../src/features/receita/mockData.ts'
import { periodosDiagnostico } from '../src/features/receita/periodos.ts'
import type { ConsultaReceita } from '../src/features/receita/tipos.ts'

const proximo = (a: number, b: number) => Math.abs(a - b) < 1e-6 * Math.max(1, Math.abs(a), Math.abs(b))

test('decomposição: efeito volume + efeito preço = variação da receita', () => {
  const d = decompor(1000, 500, 900, 540)
  assert.ok(proximo(d.efeito_volume, (900 - 1000) * 0.5))
  assert.ok(proximo(d.efeito_preco, (0.6 - 0.5) * 900))
  assert.ok(proximo(d.efeito_volume + d.efeito_preco, 40))
})

test('decomposição: volume zero deixa o preço nulo e atribui tudo ao volume (regra da A4)', () => {
  assert.deepEqual(decompor(0, 0, 200, 120), { preco_base_kwh: null, preco_atual_kwh: 0.6, efeito_volume: 120, efeito_preco: 0 })
  assert.deepEqual(decompor(200, 100, 0, 0), { preco_base_kwh: 0.5, preco_atual_kwh: null, efeito_volume: -100, efeito_preco: 0 })
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
  const consulta: ConsultaReceita = { ...recorteInicial, ...periodosDiagnostico }
  const analise = analiseReceitaMock(consulta)
  const destino = aprofundar(recorteInicial, analise.linhas[0])
  assert.equal(destino?.agrupar_por, 'bairro')
  assert.equal(destino?.municipio, analise.linhas[0].municipio)
  const noBairro = { municipio: 'Recife', bairro: 'Madalena', classe: null, agrupar_por: 'classe' as const }
  const linhaClasse = analiseReceitaMock({ ...noBairro, ...periodosDiagnostico }).linhas[0]
  assert.equal(aprofundar(noBairro, linhaClasse), null)
})

test('dados de layout são coerentes: linhas somam o total e os efeitos fecham a variação', () => {
  for (const agrupar_por of ['municipio', 'bairro', 'classe'] as const) {
    const analise = analiseReceitaMock({ ...recorteInicial, agrupar_por, ...periodosDiagnostico })
    const soma = (campo: 'receita_base' | 'receita_atual' | 'energia_base_kwh' | 'energia_atual_kwh') =>
      analise.linhas.reduce((t, l) => t + l[campo], 0)
    for (const campo of ['receita_base', 'receita_atual', 'energia_base_kwh', 'energia_atual_kwh'] as const) {
      assert.ok(proximo(soma(campo), analise.total[campo]), `${agrupar_por}: ${campo}`)
    }
    for (const linha of [analise.total, ...analise.linhas]) {
      assert.ok(proximo(linha.efeito_volume + linha.efeito_preco, linha.variacao_receita), `${agrupar_por}: ${linha.chave}`)
    }
    assert.equal(analise.fonte, 'receita_decomposicao')
    assert.deepEqual(analise.linhas.map((l) => l.variacao_receita), [...analise.linhas].map((l) => l.variacao_receita).sort((a, b) => a - b))
  }
  const personalizado = analiseReceitaMock({ ...recorteInicial, periodo: { inicio: '2026-01', fim: '2026-06' }, referencia: { inicio: '2025-01', fim: '2025-06' } })
  assert.equal(personalizado.fonte, 'fato_segmento_mensal')
  assert.equal(personalizado.serie.length, 12)
})
