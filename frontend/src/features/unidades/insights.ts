import { formatarCompetencia } from './formatters.ts'

/**
 * Meses dos insights da UC: o último com histórico e o mesmo mês do ano anterior (mesma sazonalidade do
 * gráfico de consumo). Sem esse mês, o backend compara com o mês anterior. O backend também compara
 * com a média dos 6 meses anteriores ao mês analisado.
 */
export function competenciasInsights(disponiveis: string[]) {
  const atual = disponiveis.at(-1)
  if (!atual) return { params: {}, descricao: 'Leitura automática desta unidade' }
  const anoAnterior = `${Number(atual.slice(0, 4)) - 1}${atual.slice(4)}`
  return disponiveis.includes(anoAnterior)
    ? { params: { competencia_atual: atual, competencia_referencia: anoAnterior },
        descricao: `${formatarCompetencia(atual)} comparado a ${formatarCompetencia(anoAnterior)} e aos 6 meses anteriores` }
    : { params: { competencia_atual: atual }, descricao: `${formatarCompetencia(atual)} comparado ao mês anterior e aos 6 meses anteriores` }
}
