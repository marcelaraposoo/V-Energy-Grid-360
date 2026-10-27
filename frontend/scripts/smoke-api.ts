// Teste rápido de integração: chama as rotas do backend pelo mesmo cliente que o frontend usa.
//
//   1) suba o backend:      cd backend && uvicorn app.main:app --port 8000
//   2) rode (Node 24+):     cd frontend && node scripts/smoke-api.ts
//
// Opções:  node scripts/smoke-api.ts [url-do-backend] [--com-ordens]
// Por padrão só LÊ dados. Com --com-ordens também cria, inicia e conclui uma ordem de inspeção.
import { createApi } from '../src/api/endpoints.ts'
import { ApiError, createHttp } from '../src/api/http.ts'

const argumentos = process.argv.slice(2)
const comOrdens = argumentos.includes('--com-ordens')
const url = argumentos.find((a) => !a.startsWith('--')) ?? process.env.VITE_API_URL ?? 'http://localhost:8000'
const api = createApi(createHttp(url))

let falhas = 0
async function passo<T>(nome: string, fn: () => Promise<T>, resumo?: (r: T) => string): Promise<T | undefined> {
  try {
    const r = await fn()
    console.log(`  ok   ${nome}${resumo ? `  ->  ${resumo(r)}` : ''}`)
    return r
  } catch (erro) {
    falhas++
    console.log(`  FALHA ${nome}  ->  ${erro instanceof Error ? erro.message : String(erro)}`)
  }
}

async function esperaErro(nome: string, fn: () => Promise<unknown>, status: number) {
  try {
    await fn()
    falhas++
    console.log(`  FALHA ${nome}  ->  deveria ter dado erro ${status}`)
  } catch (erro) {
    if (erro instanceof ApiError && erro.status === status) console.log(`  ok   ${nome}  ->  ${status}: ${erro.detail}`)
    else {
      falhas++
      console.log(`  FALHA ${nome}  ->  ${erro instanceof Error ? erro.message : String(erro)}`)
    }
  }
}

console.log(`Backend: ${url}`)
const saude = await passo('health', () => api.health(), (r) => `${r.status}, dados: ${r.data_source}`)
if (!saude) {
  console.log('\nO backend não respondeu. Suba o uvicorn (porta 8000) e tente de novo.')
  process.exit(1)
}

await passo('filtros', () => api.filtros(), (r) => `${r.municipios.length} municípios, ${r.competencias.length} competências`)
await passo('dashboard.kpis', () => api.dashboard.kpis(), (r) => `${r.kpis.length} indicadores`)
await passo('dashboard.serie', () => api.dashboard.serie({ classe: 'B1' }), (r) => `${r.length} meses`)
for (const agrupar_por of ['municipio', 'bairro', 'classe'] as const) {
  await passo(`receita.variacao (${agrupar_por})`, () => api.receita.variacao({ agrupar_por }), (r) => `${r.linhas.length} linhas`)
}
const ucs = await passo('unidades.buscar', () => api.unidades.buscar({ limite: 3 }), (r) => r.map((u) => u.uc_id).join(', '))
if (ucs?.[0]) {
  const uc = ucs[0].uc_id
  await passo('unidades.visao360', () => api.unidades.visao360(uc), (r) => `${r.consumo.length} meses, conta alta: ${r.diagnostico_conta_alta.mensagem}`)
}
await esperaErro('unidades.visao360 de UC inexistente', () => api.unidades.visao360('UC99999'), 404)
await esperaErro('filtro inválido', () => api.dashboard.kpis({ municipio: 'Narnia' }), 422)

const fila = await passo('perdas.fila', () => api.perdas.fila({ tamanho: 3 }), (r) => `${r.itens.length} de ${r.total} suspeitas`)
await passo('perdas.listarOrdens', () => api.perdas.listarOrdens(), (r) => `${r.length} ordens`)
if (comOrdens && fila?.itens[0]) {
  const ordem = await passo('perdas.criarOrdem', () => api.perdas.criarOrdem({ uc_id: fila.itens[0].uc_id }), (r) => `#${r.id} ${r.status}`)
  if (ordem) {
    await passo('perdas.iniciarOrdem', () => api.perdas.iniciarOrdem(ordem.id), (r) => r.status)
    await passo('perdas.registrarResultado', () => api.perdas.registrarResultado(ordem.id, { tipo: 'nenhuma' }), (r) => r.status)
    await passo('perdas.obterOrdem', () => api.perdas.obterOrdem(ordem.id), (r) => r.status)
    await esperaErro('cancelar ordem concluída', () => api.perdas.cancelarOrdem(ordem.id), 409)
  }
}

const ranking = await passo('continuidade.alimentadores', () => api.continuidade.alimentadores(), (r) => `pior: ${r[0]?.alimentador_id}`)
if (ranking?.[0]) {
  const alim = ranking[0].alimentador_id
  await passo('continuidade.serie', () => api.continuidade.serie(alim), (r) => `${r.length} meses`)
}
await passo('ia.insights (receita)', () => api.ia.insights('receita'), (r) => `${r.length} insights`)
await passo('ia.perguntar', () => api.ia.perguntar({ pergunta: 'teste de integração' }), (r) => r.status)
await passo('ia.limparSessao', () => api.ia.limparSessao('smoke'), () => '204')

console.log(falhas === 0 ? '\nTudo certo: o frontend consegue usar todas as rotas.' : `\n${falhas} falha(s).`)
process.exit(falhas === 0 ? 0 : 1)
