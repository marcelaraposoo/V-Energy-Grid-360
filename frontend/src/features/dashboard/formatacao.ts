import type { Periodo } from '../../api/types'

const competencia = new Intl.DateTimeFormat('pt-BR', { month: 'short', year: 'numeric', timeZone: 'UTC' })

export function formatarCompetencia(mes: string) {
  return competencia.format(new Date(`${mes}-01T00:00:00Z`)).replace(' de ', '/').replace('.', '')
    .replace(/^./, (letra) => letra.toUpperCase())
}

export function formatarPeriodo(periodo: Periodo) {
  const inicio = formatarCompetencia(periodo.inicio)
  const fim = formatarCompetencia(periodo.fim)
  if (periodo.inicio === periodo.fim) return fim
  return periodo.inicio.slice(0, 4) === periodo.fim.slice(0, 4)
    ? `${inicio.split('/')[0]}–${fim}` : `${inicio}–${fim}`
}

export function disponivel(valor: number | null | undefined): valor is number {
  return typeof valor === 'number' && Number.isFinite(valor)
}
