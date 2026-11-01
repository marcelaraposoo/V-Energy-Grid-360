// Dados fictícios exclusivos da apresentação do layout. Não representam uma consulta à Gold.
// Receita sem tributos e consumo em R$ e kWh, respectivamente.
import type { Periodo } from '../../api/types'
import { deslocarMes, quantidadeMeses } from '../../utils/periodosDashboard'

export const dashboardMock = {
  inicioBase: '2022-07',
  meses: [
    'Jul',
    'Ago',
    'Set',
    'Out',
    'Nov',
    'Dez',
    'Jan',
    'Fev',
    'Mar',
    'Abr',
    'Mai',
    'Jun',
  ],
  atual: {
    inicio: '2025-07',
    fim: '2026-06',
    periodo: 'Jul/2025 a Jun/2026',
    receita: [
      14.1, 14.5, 14.9, 14.8, 15.1, 15.8, 16.1, 15.3, 14.9, 14.4, 14.7, 15.4,
    ].map((valor) => valor * 1_000_000),
    consumo: [
      18.8, 19, 18.5, 18.8, 19.1, 19.7, 20.1, 19.4, 18.8, 18.5, 18.2, 17.9,
    ].map((valor) => valor * 1_000_000),
  },
  referencia: {
    inicio: '2024-07',
    fim: '2025-06',
    periodo: 'Jul/2024 a Jun/2025',
    receita: [
      13.2, 13.5, 13.8, 13.7, 14, 14.6, 14.9, 14.2, 13.8, 13.3, 13.6, 14.1,
    ].map((valor) => valor * 1_000_000),
    consumo: [
      19.5, 19.8, 19.3, 19.4, 19.8, 20.5, 20.9, 20.2, 19.5, 19.3, 19, 18.3,
    ].map((valor) => valor * 1_000_000),
  },
  indicadores: {
    ucsFaturadas: 44_820,
    ucsFaturadasReferencia: 43_940,
    ucsCadastradas: 45_000,
    ucsGd: 3_420,
    atendimentos: 84_300,
    satisfacao: 4.1,
  },
}

// Recorta somente os valores fictícios já existentes; não inventa os meses anteriores.
export function dadosPeriodoMock(periodo: Periodo) {
  const meses = new Map<string, { receita: number; consumo: number }>()
  for (const serie of [dashboardMock.referencia, dashboardMock.atual]) {
    serie.receita.forEach((receita, i) => meses.set(deslocarMes(serie.inicio, i), { receita, consumo: serie.consumo[i] }))
  }
  const selecionados = Array.from({ length: quantidadeMeses(periodo) }, (_, i) => meses.get(deslocarMes(periodo.inicio, i)))
  if (selecionados.some((m) => !m)) return null
  return { receita: selecionados.map((m) => m!.receita), consumo: selecionados.map((m) => m!.consumo) }
}
