import { ArrowDownRight, ArrowUpRight, Minus, Users } from 'lucide-react'
import type { ApiState, CadastroGdResponse, Periodo } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { disponivel, formatarCompetencia, formatarPeriodo } from './formatacao'

const numero = new Intl.NumberFormat('pt-BR')
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const variacao = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

export function UcsGdCard({ estado: { data, loading, error, reload }, competencia, referencia }: {
  estado: ApiState<CadastroGdResponse>; competencia: string; referencia: Periodo | null
}) {
  const quantidade = data?.atual.qtd_ucs_cadastradas
  const gd = data?.atual.qtd_ucs_com_gd
  const participacao = data?.atual.percentual_gd
  const diferenca = referencia && disponivel(quantidade) && disponivel(data?.referencia?.qtd_ucs_cadastradas) ? data?.variacao_cadastradas_pct : null
  const Seta = diferenca === 0 ? Minus : disponivel(diferenca) && diferenca < 0 ? ArrowDownRight : ArrowUpRight
  return <Panel title="UCs cadastradas e geração distribuída" description={`Base em ${formatarCompetencia(competencia)}`} actions={<Users size={18} aria-hidden="true" />}>
    {loading ? <LoadingState label="Carregando cadastro e GD…" />
      : error ? <ErrorState error={error} onRetry={reload} />
        : <div className="dashboard-secondary-body dashboard-cadastro-body">
          <p className={`dashboard-secondary-value${disponivel(quantidade) ? '' : ' dashboard-inadimplencia-unavailable'}`}>
            {disponivel(quantidade) ? <>{numero.format(quantidade)}<small>UCs cadastradas</small></> : 'Indisponível'}
          </p>
          <p className="dashboard-cadastro-gd">{disponivel(gd) ? numero.format(gd) : 'Indisponível'} com geração distribuída
            {' · '}{disponivel(participacao) ? `${percentual.format(participacao)}%` : 'Percentual indisponível'}</p>
          {referencia && disponivel(diferenca) && <p className="dashboard-kpi-comparison">
            <span><Seta size={14} aria-hidden="true" />{variacao.format(diferenca)}%</span> vs. cadastradas em {formatarCompetencia(referencia.fim)}
          </p>}
          {referencia && data?.referencia && <span className="sr-only">Referência: {formatarPeriodo(referencia)}. GD: {disponivel(data.referencia.qtd_ucs_com_gd) ? numero.format(data.referencia.qtd_ucs_com_gd) : 'indisponível'}.</span>}
        </div>}
  </Panel>
}
