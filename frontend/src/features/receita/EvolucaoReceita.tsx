import { useState } from 'react'
import { ChartNoAxesCombined } from 'lucide-react'
import type { Periodo, SeriePonto } from '../../api/types'
import { EmptyState } from '../../components/ui/EmptyState'
import { Panel } from '../../components/ui/Panel'
import { valoresMensais } from '../dashboard/consultas'
import { EvolucaoChart } from '../dashboard/EvolucaoChart'
import { escalaGrafico, unidadeDaEscala } from '../dashboard/escalaGrafico'

type Metrica = 'energia_kwh' | 'preco' | 'receita'
const metricas: { valor: Metrica; rotulo: string; descricao: string }[] = [
  { valor: 'energia_kwh', rotulo: 'Volume', descricao: 'Energia faturada por mês' },
  { valor: 'preco', rotulo: 'Preço médio', descricao: 'Receita de energia / energia faturada' },
  { valor: 'receita', rotulo: 'Receita', descricao: 'Receita de energia sem tributos' },
]

export function EvolucaoReceita({ serie, periodo, referencia }: { serie: SeriePonto[]; periodo: Periodo; referencia: Periodo }) {
  const [metrica, setMetrica] = useState<Metrica>('energia_kwh')
  // O gráfico do Dashboard lê `receita` ou `energia_kwh`; o preço médio (tarifa_media da API) entra no lugar da receita.
  const pontos = metrica === 'preco' ? serie.map((p) => ({ ...p, receita: p.tarifa_media })) : serie
  const campo = metrica === 'energia_kwh' ? 'energia_kwh' : 'receita'
  const atual = valoresMensais(pontos, periodo, campo)
  const base = valoresMensais(pontos, referencia, campo)
  const selecionada = metricas.find((m) => m.valor === metrica)!
  // Mesma escala do gráfico, para a unidade do título acompanhar o eixo (ex.: "milhões de kWh").
  const { prefixo } = escalaGrafico([...(atual ?? []), ...(base ?? [])])
  const unidade = metrica === 'preco' ? 'R$/kWh' : unidadeDaEscala(metrica === 'energia_kwh' ? 'kWh' : 'R$', prefixo)
  return (
    <Panel title="Evolução mensal" description={`${selecionada.descricao} · ${unidade}`}
      actions={<div className="segmented" role="group" aria-label="Métrica">
        {metricas.map((m) => <button key={m.valor} type="button" className="button button--secondary" aria-pressed={metrica === m.valor}
          onClick={() => setMetrica(m.valor)}>{m.rotulo}</button>)}
      </div>}>
      {atual ? <EvolucaoChart key={`${metrica}-${periodo.inicio}-${referencia.inicio}`} titulo={`${selecionada.rotulo} mensal`}
        unidade={metrica === 'energia_kwh' ? 'kWh' : 'R$'} atual={atual} referencia={base ?? undefined} periodoAtual={periodo} periodoReferencia={referencia} />
        : <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período" description="Não há dados mensais completos no intervalo selecionado." compact />}
    </Panel>
  )
}
