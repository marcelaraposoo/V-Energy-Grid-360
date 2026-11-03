import { Banknote, CircleDollarSign, Zap } from 'lucide-react'
import type { ApiState, KpisResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { KpiCard } from '../../components/ui/KpiCard'
import { explicacoes, kwh, reais, tarifa } from '../../utils/indicadores'
import { disponivel, formatarPeriodo } from './formatacao'

const indicadores = [
  { nome: 'Receita faturada', titulo: 'Receita de energia', icone: Banknote, info: explicacoes.receita, formatar: reais, colorir: true },
  { nome: 'Energia faturada', titulo: 'Energia faturada', icone: Zap, info: explicacoes.energia, formatar: kwh, colorir: true },
  { nome: 'Tarifa média efetiva', titulo: 'Preço médio por kWh', icone: CircleDollarSign, info: explicacoes.preco, formatar: tarifa, colorir: false },
]

export function KpisPrincipais({ estado: { data, loading, error, reload }, referencia }: { estado: ApiState<KpisResponse>; referencia: Periodo | null }) {
  return (
    <section className="dashboard-kpis" aria-label="Indicadores principais" aria-busy={loading}>
      {loading ? <div className="dashboard-kpis-feedback"><LoadingState label="Carregando indicadores…" /></div>
        : error ? <div className="dashboard-kpis-feedback"><ErrorState error={error} onRetry={reload} /></div>
          : indicadores.map(({ nome, titulo, icone, info, formatar, colorir }) => {
            const kpi = data?.kpis.find((item) => item.nome === nome)
            const comparavel = disponivel(kpi?.valor_atual) && disponivel(kpi?.valor_base)
            return <KpiCard key={nome} titulo={titulo} icone={icone} info={info} colorir={colorir}
              valor={disponivel(kpi?.valor_atual) ? formatar(kpi.valor_atual) : '—'}
              referencia={referencia && { valor: disponivel(kpi?.valor_base) ? formatar(kpi.valor_base) : '—', periodo: formatarPeriodo(referencia) }}
              variacao={comparavel ? kpi?.variacao_pct ?? null : null} />
          })}
    </section>
  )
}
