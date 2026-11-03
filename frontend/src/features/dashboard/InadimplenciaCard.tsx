import type { ApiState, KpisResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { dataCorteGold, formatarData, quantidadeMeses } from '../../utils/periodosDashboard'
import { disponivel, formatarPeriodo } from './formatacao'

const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const diferenca = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

type Props = {
  periodo: Periodo
  referencia: Periodo | null
  estado: ApiState<KpisResponse>
}

// A taxa da última competência não aparece: é o mês com mais faturas ainda não vencidas na data de corte,
// e a contagem do contrato as trata como em aberto.
export function InadimplenciaCard({ periodo, referencia, estado: { data, loading, error, reload } }: Props) {
  const kpi = data?.kpis.find((item) => item.nome === 'Inadimplência')
  const variosMeses = quantidadeMeses(periodo) > 1
  const variacao = referencia && disponivel(kpi?.valor_atual) && disponivel(kpi?.valor_base) ? kpi?.variacao_pp : null
  const tendencia = disponivel(variacao) && variacao !== 0
    ? variacao < 0 ? 'favoravel' : 'desfavoravel' : undefined
  const corte = formatarData(kpi?.inadimplencia?.data_corte ?? dataCorteGold)

  return (
    <Panel title="Faturamento em aberto" info={<>
      Parte do valor faturado no período (com tributos) que continua em aberto em {corte}, a data de corte da base.
      Cada fatura conta na sua competência. <strong>Inclui faturas que ainda não tinham vencido nessa data.</strong>{' '}
      Atrasos de faturas já pagas não entram.
    </>}>
      {loading ? <LoadingState label="Carregando faturamento em aberto…" />
        : error ? <ErrorState error={error} onRetry={reload} title="Não foi possível consultar o faturamento em aberto" />
          : <div className="dashboard-secondary-body">
            <div className="dashboard-secondary-main">
              <p className={`dashboard-secondary-value${disponivel(kpi?.valor_atual) ? '' : ' dashboard-inadimplencia-unavailable'}`}>
                {disponivel(kpi?.valor_atual) ? <>{percentual.format(kpi.valor_atual)}<small>%</small></> : 'Indisponível'}
              </p>
              <p>{variosMeses ? 'Consolidado' : 'Competência'} · {formatarPeriodo(periodo)}</p>
              {referencia && disponivel(variacao) && <p className="dashboard-inadimplencia-comparison">
                <strong data-tendencia={tendencia}>{diferenca.format(variacao).replace('-', '−')} p.p.</strong> vs. referência  ({formatarPeriodo(referencia)})
              </p>}
            </div>
          </div>}
    </Panel>
  )
}
