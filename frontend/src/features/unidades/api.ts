import type { SelecaoContaAlta, Visao360 } from './types'

const apiUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export async function consultarVisao360(
  id: string,
  comparacao: SelecaoContaAlta | null,
  signal: AbortSignal,
): Promise<Visao360> {
  const query = new URLSearchParams()
  if (comparacao?.competencia_atual)
    query.set('competencia_atual', comparacao.competencia_atual)
  if (comparacao?.competencia_referencia)
    query.set('competencia_referencia', comparacao.competencia_referencia)
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
