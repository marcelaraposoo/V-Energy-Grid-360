import { Wallet } from 'lucide-react'
import type { ApiState, KpisResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { quantidadeMeses } from '../../utils/periodosDashboard'

const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const diferenca = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const competencia = new Intl.DateTimeFormat('pt-BR', { month: 'short', year: 'numeric', timeZone: 'UTC' })

function formatarMes(mes: string) {
  return competencia.format(new Date(`${mes}-01T00:00:00Z`)).replace(' de ', '/').replace('.', '')
    .replace(/^./, (letra) => letra.toUpperCase())
}

function formatarPeriodo(periodo: Periodo) {
  const inicio = formatarMes(periodo.inicio)
  const fim = formatarMes(periodo.fim)
  if (periodo.inicio === periodo.fim) return fim
  return periodo.inicio.slice(0, 4) === periodo.fim.slice(0, 4)
    ? `${inicio.split('/')[0]}–${fim}` : `${inicio}–${fim}`
}

function disponivel(valor: number | null | undefined): valor is number {
  return typeof valor === 'number' && Number.isFinite(valor)
}

type Props = {
  periodo: Periodo
  referencia: Periodo | null
  estado: ApiState<KpisResponse>
}

export function InadimplenciaCard({ periodo, referencia, estado: { data, loading, error, reload } }: Props) {
  const kpi = data?.kpis.find((item) => item.nome === 'Inadimplência')
  const variosMeses = quantidadeMeses(periodo) > 1
  const ultima = kpi?.inadimplencia?.ultima_competencia_pct
  const variacao = referencia && disponivel(kpi?.valor_atual) && disponivel(kpi?.valor_base) ? kpi?.variacao_pp : null

  return (
    <Panel title="Faturamento em aberto" actions={<Wallet size={18} aria-hidden="true" />}>
      {loading ? <LoadingState label="Carregando faturamento em aberto…" />
        : error ? <ErrorState error={error} onRetry={reload} title="Não foi possível consultar o faturamento em aberto" />
          : <div className="dashboard-secondary-body"
              title={kpi?.inadimplencia ? 'Situação conhecida até 30/06/2026' : undefined}>
            <div className="dashboard-secondary-main">
              <p className={`dashboard-secondary-value${disponivel(kpi?.valor_atual) ? '' : ' dashboard-inadimplencia-unavailable'}`}>
                {disponivel(kpi?.valor_atual) ? <>{percentual.format(kpi.valor_atual)}<small>%</small></> : 'Indisponível'}
              </p>
              <p>{variosMeses ? 'Consolidado' : 'Competência'} · {formatarPeriodo(periodo)}</p>
              {referencia && disponivel(variacao) && <p className="dashboard-inadimplencia-comparison">
                <strong>{diferenca.format(variacao)} p.p.</strong> vs. referência · {formatarPeriodo(referencia)}
              </p>}
            </div>
            {variosMeses && <div className="dashboard-secondary-detail dashboard-inadimplencia-last">
              <p className={`dashboard-secondary-value${disponivel(ultima) ? '' : ' dashboard-inadimplencia-unavailable'}`}>
                {disponivel(ultima) ? <>{percentual.format(ultima)}<small>%</small></> : 'Indisponível'}
              </p>
              <p>Última competência · {formatarMes(periodo.fim)}</p>
            </div>}
          </div>}
    </Panel>
  )
}
