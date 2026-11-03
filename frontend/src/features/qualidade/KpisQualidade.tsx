import { Clock, Repeat, TimerOff, ZapOff } from 'lucide-react'
import type { ReactNode } from 'react'
import type { IndicadoresContinuidade, Periodo } from '../../api/types'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { KpiCard } from '../../components/ui/KpiCard'
import { formatarPeriodo } from '../dashboard/formatacao'
import { horas, horasImpacto, quantidade, variacaoPct, vezes } from './formatacao'

type Campo = 'dec_horas' | 'fec_vezes' | 'qtd_interrupcoes' | 'horas_interrompidas'

const indicadores: { campo: Campo; titulo: string; icone: typeof Clock; formatar: (v: number) => string; info: ReactNode }[] = [
  {
    campo: 'dec_horas', titulo: 'DEC', icone: Clock, formatar: horas,
    info: <InfoTipContent resumo="Duração equivalente: horas que, em média, cada unidade consumidora ficou sem energia no período."
     nota="Cada ocorrência registrada corresponde a uma UC interrompida. O cálculo se dá pela soma dos DEC mensais." />,
  },
  {
    campo: 'fec_vezes', titulo: 'FEC', icone: Repeat, formatar: vezes,
    info: <InfoTipContent resumo="Frequência equivalente: quantas vezes, em média, cada unidade consumidora ficou sem energia no período."
    nota="O cálculo se dá pela soma dos FEC mensais." />,

  },
  {
    campo: 'qtd_interrupcoes', titulo: 'Interrupções', icone: ZapOff, formatar: quantidade,
    info: <InfoTipContent resumo="Ocorrências registradas no período, de todos os tipos, inclusive oscilações." />,
  },
  {
    campo: 'horas_interrompidas', titulo: 'Horas sem energia', icone: TimerOff, formatar: horasImpacto,
    info: <InfoTipContent resumo="Soma das horas de todas as interrupções do período (UC × horas)."
      itens={[{ rotulo: 'Atenção', texto: 'Uma UC que ficou sem energia várias vezes conta várias vezes. Não é o número de consumidores afetados.' }]}
      nota="Mede o impacto total, sem dividir pelo tamanho da base. Ajuda a priorizar onde a falta pesa mais." />,
  },
]

export function KpisQualidade({ atual, base, referencia }: { atual: IndicadoresContinuidade | null; base: IndicadoresContinuidade | null; referencia: Periodo | null }) {
  return (
    <section className="qualidade-kpis" aria-label="Indicadores de continuidade">
      {indicadores.map(({ campo, titulo, icone, formatar, info }) => (
        <KpiCard key={campo} titulo={titulo} icone={icone} info={info} menorMelhor
          valor={atual ? formatar(atual[campo]) : '—'}
          referencia={referencia && { valor: base ? formatar(base[campo]) : '—', periodo: formatarPeriodo(referencia) }}
          variacao={variacaoPct(atual?.[campo], base?.[campo])} />
      ))}
    </section>
  )
}
