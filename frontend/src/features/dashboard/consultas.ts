import type { DashboardParams, Periodo, SeriePonto } from '../../api/types.ts'
import { deslocarMes, quantidadeMeses } from '../../utils/periodosDashboard.ts'

export function parametrosDashboard(periodo: Periodo, referencia: Periodo | null): DashboardParams {
  const comuns = { atual_inicio: periodo.inicio, atual_fim: periodo.fim }
  return referencia
    ? { ...comuns, comparar: true, base_inicio: referencia.inicio, base_fim: referencia.fim }
    : { ...comuns, comparar: false }
}

export function valoresMensais(serie: SeriePonto[], periodo: Periodo, campo: 'receita' | 'energia_kwh'): number[] | null {
  const porMes = new Map(serie.map((ponto) => [ponto.competencia, ponto[campo]]))
  const valores: number[] = []
  for (let i = 0; i < quantidadeMeses(periodo); i++) {
    const valor = porMes.get(deslocarMes(periodo.inicio, i))
    if (typeof valor !== 'number' || !Number.isFinite(valor)) return null
    valores.push(valor)
  }
  return valores
}
