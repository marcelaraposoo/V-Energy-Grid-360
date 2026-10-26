import type { TipoComparacaoContaAlta, Visao360 } from './types'

export const COMPARACAO_PADRAO: TipoComparacaoContaAlta =
  'trimestre_ano_anterior'

const apiUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export async function consultarVisao360(
  id: string,
  comparacao: TipoComparacaoContaAlta,
  signal: AbortSignal,
): Promise<Visao360> {
  const query = new URLSearchParams({ comparacao })
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
