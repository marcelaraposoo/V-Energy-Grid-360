import { ChartNoAxesCombined } from 'lucide-react'
import type { ApiState, Periodo, SeriePonto } from '../../api'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { valoresMensais } from './consultas'
import { EvolucaoChart } from './EvolucaoChart'
import { escalaGrafico, unidadeDaEscala } from './escalaGrafico'

export function EvolucaoPanel({ estado: { data, loading, error, reload }, periodo, referencia, campo }: {
  estado: ApiState<SeriePonto[]>; periodo: Periodo; referencia: Periodo | null; campo: 'receita' | 'energia_kwh'
}) {
  const receita = campo === 'receita'
  const atual = data ? valoresMensais(data, periodo, campo) : null
  const base = data && referencia ? valoresMensais(data, referencia, campo) : null
  const escala = escalaGrafico([...(atual ?? []), ...(base ?? [])])
  const unidade = unidadeDaEscala(receita ? 'R$' : 'kWh', escala.prefixo)
  return <Panel title={receita ? 'Evolução da receita' : 'Evolução do consumo faturado'}
    description={receita ? `Receita de energia, sem tributos · ${unidade}` : `Energia faturada · ${unidade}`}>
    {loading ? <LoadingState label="Carregando evolução mensal…" />
      : error ? <ErrorState error={error} onRetry={reload} />
        : atual ? <EvolucaoChart key={`${periodo.inicio}-${periodo.fim}-${referencia?.inicio}-${referencia?.fim}`}
            titulo={receita ? 'Receita mensal' : 'Consumo mensal'} unidade={receita ? 'R$' : 'kWh'}
            atual={atual} referencia={base ?? undefined} periodoAtual={periodo} periodoReferencia={referencia} />
          : <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período" description="Não há dados mensais completos no intervalo selecionado." compact />}
  </Panel>
}
