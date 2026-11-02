import type { DashboardParams, Periodo } from '../../api/types.ts'
import { parametrosDashboard } from './consultas.ts'

export function parametrosInadimplencia(periodo: Periodo, referencia: Periodo | null): DashboardParams {
  return { ...parametrosDashboard(periodo, referencia), indicador: 'inadimplencia' }
}
