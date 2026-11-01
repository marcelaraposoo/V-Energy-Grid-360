import type { DashboardParams, FiltrosParams, Periodo } from '../../api/types.ts'

export function parametrosInadimplencia(periodo: Periodo, referencia: Periodo | null, filtros: FiltrosParams): DashboardParams {
  const comuns = {
    indicador: 'inadimplencia' as const,
    atual_inicio: periodo.inicio,
    atual_fim: periodo.fim,
    municipio: filtros.municipio || undefined,
    bairro: filtros.bairro || undefined,
    classe: filtros.classe?.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase() || undefined,
  }
  return referencia
    ? { ...comuns, comparar: true, base_inicio: referencia.inicio, base_fim: referencia.fim }
    : { ...comuns, comparar: false }
}
