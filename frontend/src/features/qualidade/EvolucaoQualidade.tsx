import { useState } from 'react'
import { ChartNoAxesCombined } from 'lucide-react'
import type { Periodo, PontoContinuidade } from '../../api/types'
import { EmptyState } from '../../components/ui/EmptyState'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { Panel } from '../../components/ui/Panel'
import { EvolucaoChart } from '../dashboard/EvolucaoChart'
import { deslocarMes, quantidadeMeses } from '../../utils/periodosDashboard'

type Metrica = 'dec_horas' | 'fec_vezes' | 'qtd_interrupcoes'
const metricas: Record<Metrica, { rotulo: string; titulo: string; unidade: 'h' | 'un'; descricao: string }> = {
  dec_horas: { rotulo: 'DEC', titulo: 'DEC mensal', unidade: 'h', descricao: 'horas por UC' },
  fec_vezes: { rotulo: 'FEC', titulo: 'FEC mensal', unidade: 'un', descricao: 'interrupções por UC' },
  qtd_interrupcoes: { rotulo: 'Interrupções', titulo: 'Interrupções por mês', unidade: 'un', descricao: 'ocorrências' },
}

function valores(serie: PontoContinuidade[], periodo: Periodo, metrica: Metrica): number[] | null {
  const porMes = new Map(serie.map((p) => [p.competencia, p[metrica]]))
  const saida: number[] = []
  for (let i = 0; i < quantidadeMeses(periodo); i++) {
    const valor = porMes.get(deslocarMes(periodo.inicio, i))
    if (valor === undefined) return null
    saida.push(valor)
  }
  return saida
}

export function EvolucaoQualidade({ serie, serieBase, periodo, referencia, escopo }: {
  serie: PontoContinuidade[]; serieBase: PontoContinuidade[]; periodo: Periodo; referencia: Periodo | null; escopo: string
}) {
  const [metrica, setMetrica] = useState<Metrica>('dec_horas')
  const config = metricas[metrica]
  const atual = valores(serie, periodo, metrica)
  const base = referencia ? valores(serieBase, referencia, metrica) : null
  return (
    <Panel title="Evolução mensal" description={`${escopo} · ${config.descricao}`} className="qualidade-evolucao"
      info={<InfoTipContent resumo="Indicador de cada mês do período, comparado à referência quando ela está ativa."
        nota="Somando os DEC (ou FEC) mensais, obtém-se o valor do período mostrado no card." />}
      actions={<div className="segmented" role="group" aria-label="Indicador do gráfico">
        {(Object.keys(metricas) as Metrica[]).map((m) => (
          <button key={m} type="button" className="button button--secondary" aria-pressed={metrica === m}
            onClick={() => setMetrica(m)}>{metricas[m].rotulo}</button>
        ))}
      </div>}>
      {atual ? <EvolucaoChart key={`${metrica}-${periodo.inicio}-${periodo.fim}-${referencia?.inicio}-${referencia?.fim}-${escopo}`}
        titulo={config.titulo} unidade={config.unidade} atual={atual} referencia={base ?? undefined}
        periodoAtual={periodo} periodoReferencia={referencia} />
        : <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período" description="Não há indicadores mensais completos para o recorte selecionado." compact />}
    </Panel>
  )
}
