import type { AbaFaturas, PaginaFaturasUC, PeriodoHistorico, SituacaoFaturas, Visao360 } from './types'

const apiUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export async function consultarFaturas(
  id: string,
  aba: AbaFaturas,
  ano: string,
  situacao: SituacaoFaturas,
  pagina: number,
  signal: AbortSignal,
): Promise<PaginaFaturasUC> {
  const query = new URLSearchParams({ aba, pagina: String(pagina) })
  if (aba === 'historico') {
    if (ano) query.set('ano', ano)
    query.set('situacao', situacao)
  }
  const resposta = await fetch(`${apiUrl}/api/unidades/${encodeURIComponent(id)}/faturas?${query}`, { signal })
  if (!resposta.ok) throw new Error('Não foi possível consultar as faturas. Tente novamente.')
  return resposta.json()
}

export async function consultarVisao360(
  id: string,
  periodoInterrupcoes: PeriodoHistorico,
  signal: AbortSignal,
): Promise<Visao360> {
  const query = new URLSearchParams()
  query.set('periodo_interrupcoes', periodoInterrupcoes)
  query.set('periodo_atendimentos', 'todos')
  const resposta = await fetch(
    `${apiUrl}/api/unidades/${encodeURIComponent(id)}/visao-360?${query}`,
    { signal },
  )
  if (!resposta.ok) {
    throw new Error(
      resposta.status === 404
        ? 'Unidade consumidora não encontrada. Confira o identificador e faça uma nova busca.'
        : 'Não foi possível consultar os dados da unidade. Tente novamente.',
    )
  }
  return resposta.json()
}
