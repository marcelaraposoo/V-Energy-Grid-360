import { ArrowDownRight, ArrowUpRight, Banknote, CircleDollarSign, Minus, Zap } from 'lucide-react'
import type { ApiState, KpisResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { disponivel, formatarPeriodo } from './formatacao'

const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const indicadores = [
  { nome: 'Receita faturada', titulo: 'Receita de energia', icone: Banknote, detalhe: 'Energia faturada, sem tributos', formatar: (v: number) => `R$ ${compacto.format(v)}` },
  { nome: 'Energia faturada', titulo: 'Consumo faturado', icone: Zap, detalhe: 'Energia faturada no período', formatar: (v: number) => `${compacto.format(v)} kWh` },
  { nome: 'Tarifa média efetiva', titulo: 'Preço médio por kWh', icone: CircleDollarSign, detalhe: 'Receita de energia / consumo faturado', formatar: (v: number) => moeda.format(v) },
]

export function KpisPrincipais({ estado: { data, loading, error, reload }, referencia }: { estado: ApiState<KpisResponse>; referencia: Periodo | null }) {
  return (
    <section className="dashboard-kpis" aria-label="Indicadores principais" aria-busy={loading}>
      {loading ? <div className="dashboard-kpis-feedback"><LoadingState label="Carregando indicadores…" /></div>
        : error ? <div className="dashboard-kpis-feedback"><ErrorState error={error} onRetry={reload} /></div>
          : indicadores.map(({ nome, titulo, icone: Icone, detalhe, formatar }) => {
            const kpi = data?.kpis.find((item) => item.nome === nome)
            const variacao = referencia && disponivel(kpi?.valor_atual) && disponivel(kpi?.valor_base) ? kpi?.variacao_pct : null
            const Seta = variacao === 0 ? Minus : disponivel(variacao) && variacao < 0 ? ArrowDownRight : ArrowUpRight
            const tendencia = (nome === 'Receita faturada' || nome === 'Energia faturada') && disponivel(variacao) && variacao !== 0
              ? variacao > 0 ? 'favoravel' : 'desfavoravel' : undefined
            return <article className="panel dashboard-kpi" key={nome}>
              <h2><Icone size={17} strokeWidth={1.5} aria-hidden="true" />{titulo}</h2>
              <p className="dashboard-kpi-value">{disponivel(kpi?.valor_atual) ? formatar(kpi.valor_atual) : '—'}</p>
              <p className="dashboard-kpi-detail">{detalhe}</p>
              {referencia && <p className="dashboard-kpi-comparison" title={`Referência: ${formatarPeriodo(referencia)}`}>
                {disponivel(variacao) ? <><span data-tendencia={tendencia}><Seta size={15} aria-hidden="true" />{percentual.format(variacao)}%</span>vs. referência</> : 'Sem dados para comparação'}
              </p>}
            </article>
          })}
    </section>
  )
}
