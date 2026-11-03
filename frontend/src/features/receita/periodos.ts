import type { Periodo } from '../../api/types.ts'
import { limitesDashboard, periodoInicialDashboard, referenciaInicialDashboard, validarPeriodosDashboard } from '../../utils/periodosDashboard.ts'

// Contrato da Gold: primeiro ano (2022-07 a 2023-06) × últimos 12 meses (2025-07 a 2026-06).
export const periodosDiagnostico = { periodo: periodoInicialDashboard, referencia: referenciaInicialDashboard }

/** Link para a Análise de Receita com os mesmos períodos (as regras de comparação são as mesmas do Dashboard). */
export function linkReceita(periodo: Periodo, referencia: Periodo | null): string {
  if (!referencia) return '/receita'
  const busca = new URLSearchParams({
    atual_inicio: periodo.inicio, atual_fim: periodo.fim, base_inicio: referencia.inicio, base_fim: referencia.fim,
  })
  return `/receita?${busca}`
}

/** Períodos recebidos pela URL; nulo se faltarem ou forem inválidos (aí a tela abre no diagnóstico). */
export function periodosDaUrl(busca: URLSearchParams): { periodo: Periodo; referencia: Periodo } | null {
  const [atualInicio, atualFim, baseInicio, baseFim] = ['atual_inicio', 'atual_fim', 'base_inicio', 'base_fim'].map((chave) => busca.get(chave))
  if (!atualInicio || !atualFim || !baseInicio || !baseFim) return null
  const periodo = { inicio: atualInicio, fim: atualFim }
  const referencia = { inicio: baseInicio, fim: baseFim }
  return validarPeriodosDashboard(periodo, referencia, true, limitesDashboard) ? null : { periodo, referencia }
}
