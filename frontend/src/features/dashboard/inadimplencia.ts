import type { DashboardParams, Periodo } from '../../api/types.ts'

export function parametrosInadimplencia(periodo: Periodo, referencia: Periodo | null): DashboardParams {
  const comuns = {
    indicador: 'inadimplencia' as const,
    atual_inicio: periodo.inicio,
    atual_fim: periodo.fim,
  }
  return referencia
    ? { ...comuns, comparar: true, base_inicio: referencia.inicio, base_fim: referencia.fim }
    : { ...comuns, comparar: false }
}
