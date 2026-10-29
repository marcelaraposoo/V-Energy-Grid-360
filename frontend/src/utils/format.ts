// Formatadores em pt-BR usados pelas telas de Inspeções e do Assistente.

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const fmtInteiro = (v: number) => inteiro.format(v)
export const fmtDecimal = (v: number) => decimal.format(v)

/** '2026-10-27T10:31:00' -> '27/10/2026 10:31'. */
export function fmtDataHora(iso: string): string {
  const [data, hora] = iso.split('T')
  const [ano, mes, dia] = data.split('-')
  const h = hora?.slice(0, 5)
  return `${dia}/${mes}/${ano}${h ? ` ${h}` : ''}`
}

/** Mensagem legível para qualquer erro de chamada à API. */
export function mensagemDeErro(erro: unknown): string {
  if (erro && typeof erro === 'object' && 'detail' in erro) {
    const detail = (erro as { detail: unknown }).detail
    if (typeof detail === 'string' && detail) return detail
  }
  return erro instanceof Error ? erro.message : 'Ocorreu um erro inesperado.'
}
