import type { DashboardParams, Periodo } from './types.ts'
import { ApiError } from './http.ts'
import { sugerirReferencia, validarPeriodosDashboard } from '../utils/periodosDashboard.ts'

export function prepararParametrosDashboard(params: DashboardParams): DashboardParams {
  const { base_inicio, base_fim, ...demais } = params
  const parAtual = [params.atual_inicio, params.atual_fim]
  if (parAtual.some(Boolean) && !parAtual.every(Boolean)) throw new ApiError(422, 'Informe início e fim do período analisado.')
  const atual: Periodo = { inicio: params.atual_inicio ?? '2025-07', fim: params.atual_fim ?? '2026-06' }
  if (params.comparar === false) {
    const erro = validarPeriodosDashboard(atual, null, false)
    if (erro) throw new ApiError(422, erro)
    return demais // Nenhum parâmetro base_* sai do cliente quando a comparação está desativada.
  }
  if (Boolean(base_inicio) !== Boolean(base_fim)) throw new ApiError(422, 'Informe início e fim do período de referência.')
  const base = base_inicio && base_fim ? { inicio: base_inicio, fim: base_fim }
    : params.atual_inicio ? sugerirReferencia(atual) : { inicio: '2022-07', fim: '2023-06' }
  const erro = validarPeriodosDashboard(atual, base, true)
  if (erro) throw new ApiError(422, erro)
  return base && params.atual_inicio && !base_inicio
    ? { ...params, base_inicio: base.inicio, base_fim: base.fim } : params
}
