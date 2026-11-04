import { ArrowDownRight, ArrowUpRight, ChartNoAxesCombined, Minus } from 'lucide-react'
import type { ApiState, ConsumoClassesResponse, ConsumoLocaisResponse, Periodo } from '../../api'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { nomesClasse, variacao as formatarVariacao } from '../../utils/indicadores'
import { ConsumoLocais } from './ConsumoLocais'
import { disponivel, formatarPeriodo } from './formatacao'

export type AgrupamentoConsumo = 'classe' | 'local'

const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export function ClassesChart({ estado: { data, loading, error, reload }, periodo, referencia, agrupamento = 'classe', onAgrupamento, locais, municipio = null, onMunicipio }: {
  estado: ApiState<ConsumoClassesResponse>; periodo: Periodo; referencia: Periodo | null
  /** Classe ou local (município na distribuidora; bairro com município escolhido). */
  agrupamento?: AgrupamentoConsumo
  onAgrupamento?: (valor: AgrupamentoConsumo) => void
  locais?: ApiState<ConsumoLocaisResponse | null>
  municipio?: string | null
  onMunicipio?: (municipio: string) => void
}) {
  const maximo = Math.max(1, ...(data?.classes.map((item) => item.consumo_kwh ?? 0) ?? []))

  const local = municipio ? 'bairro' : 'município'
  const porLocal = agrupamento === 'local' && locais
  const actions = onAgrupamento && <div className="segmented" role="group" aria-label="Agrupar energia por">
    <button type="button" className="button button--secondary" aria-pressed={agrupamento === 'classe'} onClick={() => onAgrupamento('classe')}>Classe</button>
    <button type="button" className="button button--secondary" aria-pressed={agrupamento === 'local'} onClick={() => onAgrupamento('local')}>
      {municipio ? 'Bairro' : 'Município'}
    </button>
  </div>

  if (porLocal) {
    return <Panel title={`Energia faturada por ${local}`} description={municipio ? `${municipio} · ${formatarPeriodo(periodo)}` : formatarPeriodo(periodo)}
      className="dashboard-classes-panel" actions={actions}
      info={`Energia faturada (kWh) de cada ${local} no período, do maior para o menor. Com referência, a variação compara o mesmo ${local} nos dois períodos.${municipio ? '' : ' Clique num município para filtrar o Dashboard.'}`}>
      {locais.loading ? <LoadingState label={`Carregando consumo por ${local}…`} />
        : locais.error ? <ErrorState error={locais.error} onRetry={locais.reload} />
          : locais.data && <ConsumoLocais dados={locais.data} periodo={periodo} referencia={referencia} onMunicipio={onMunicipio} />}
    </Panel>
  }

  return <Panel title="Energia faturada por classe" description={formatarPeriodo(periodo)} className="dashboard-classes-panel" actions={actions}
    info="Energia faturada (kWh) de cada classe no período. Com referência, a variação compara a mesma classe nos dois períodos.">
    {loading ? <LoadingState label="Carregando consumo por classe…" />
      : error ? <ErrorState error={error} onRetry={reload} />
        : !data?.classes.length ? <EmptyState icon={ChartNoAxesCombined} title="Sem dados por classe" description="Não há dados disponíveis no período selecionado." compact />
          : <div className="dashboard-classes-content">
            <ul className="dashboard-classes-list" aria-label="Volume de energia faturada por classe">
              {data.classes.map((item) => {
                const valor = item.consumo_kwh
                const mudanca = referencia && disponivel(valor) && disponivel(item.consumo_referencia_kwh) ? item.variacao_pct : null
                const Seta = mudanca === 0 ? Minus : disponivel(mudanca) && mudanca < 0 ? ArrowDownRight : ArrowUpRight
                const tendencia = disponivel(mudanca) && mudanca !== 0
                  ? mudanca > 0 ? 'favoravel' : 'desfavoravel' : undefined
                return <li key={item.classe}>
                  <div className="dashboard-class-row dashboard-class-row--estatica" data-classe={item.classe}>
                    <span className="dashboard-class-heading">
                      <span>{nomesClasse[item.classe]}</span>
                      <span className="dashboard-class-volume">{disponivel(valor) ? `${compacto.format(valor)} kWh` : 'Indisponível'}
                        {disponivel(item.participacao_pct) && <small> · {percentual.format(item.participacao_pct)}%</small>}
                      </span>
                    </span>
                    <span className="dashboard-class-measure">
                      <span className="dashboard-class-track" aria-hidden="true">
                        <span className="dashboard-class-bar" style={{ width: `${disponivel(valor) ? valor / maximo * 100 : 0}%` }} />
                      </span>
                      {referencia && <span className="dashboard-class-change" data-tendencia={tendencia}>
                        {disponivel(mudanca) ? <><Seta size={13} aria-hidden="true" />{formatarVariacao(mudanca)}</> : '—'}
                      </span>}
                    </span>
                  </div>
                </li>
              })}
            </ul>
            <p className="dashboard-classes-note">{referencia ? `Variação vs. referência · ${formatarPeriodo(referencia)}` : 'Participação no consumo total do período'}
              {data.consumo_total_kwh === null ? ' · Participação indisponível: dados incompletos ou inválidos.' : data.consumo_total_kwh === 0 ? ' · Participação indefinida: consumo total zero.' : ''}
            </p>
          </div>}
  </Panel>
}
