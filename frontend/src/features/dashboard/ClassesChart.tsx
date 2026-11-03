import { useId, useRef, useState } from 'react'
import { ArrowDownRight, ArrowUpRight, ChartNoAxesCombined, Minus } from 'lucide-react'
import type { ApiState, ClasseConsumo, ConsumoClasse, ConsumoClassesResponse, Periodo } from '../../api'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { nomesClasse, variacao as formatarVariacao } from '../../utils/indicadores'
import { disponivel, formatarPeriodo } from './formatacao'

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const completo = (valor: number | null) => disponivel(valor) ? `${numero.format(valor)} kWh` : 'Indisponível'

export function ClassesChart({ estado: { data, loading, error, reload }, periodo, referencia }: {
  estado: ApiState<ConsumoClassesResponse>; periodo: Periodo; referencia: Periodo | null
}) {
  const [tooltip, setTooltip] = useState<{ classe: ClasseConsumo; top: number } | null>(null)
  const corpoRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()
  const maximo = Math.max(1, ...(data?.classes.map((item) => item.consumo_kwh ?? 0) ?? []))
  const detalheTooltip = data?.classes.find((item) => item.classe === tooltip?.classe)

  function mostrar(item: ConsumoClasse, linha: HTMLButtonElement) {
    const corpo = corpoRef.current?.getBoundingClientRect()
    if (!corpo) return
    const top = Math.max(8, linha.getBoundingClientRect().top - corpo.top - (referencia ? 100 : 66))
    setTooltip({ classe: item.classe, top })
  }

  return <Panel title="Energia faturada por classe" description={formatarPeriodo(periodo)} className="dashboard-classes-panel"
    info="Energia faturada (kWh) de cada classe no período. Participação = energia da classe ÷ energia total. Com referência, a variação compara a mesma classe nos dois períodos.">
    {loading ? <LoadingState label="Carregando consumo por classe…" />
      : error ? <ErrorState error={error} onRetry={reload} />
        : !data?.classes.length ? <EmptyState icon={ChartNoAxesCombined} title="Sem dados por classe" description="Não há dados disponíveis no período selecionado." compact />
          : <div className="dashboard-classes-content" ref={corpoRef}>
            <ul className="dashboard-classes-list" aria-label="Volume de energia faturada por classe">
              {data.classes.map((item) => {
                const valor = item.consumo_kwh
                const mudanca = referencia && disponivel(valor) && disponivel(item.consumo_referencia_kwh) ? item.variacao_pct : null
                const Seta = mudanca === 0 ? Minus : disponivel(mudanca) && mudanca < 0 ? ArrowDownRight : ArrowUpRight
                const tendencia = disponivel(mudanca) && mudanca !== 0
                  ? mudanca > 0 ? 'favoravel' : 'desfavoravel' : undefined
                return <li key={item.classe}>
                  <button type="button" className="dashboard-class-row" data-classe={item.classe}
                    aria-describedby={tooltip?.classe === item.classe ? tooltipId : undefined}
                    onPointerEnter={(event) => { if (event.pointerType === 'mouse') mostrar(item, event.currentTarget) }}
                    onPointerLeave={(event) => { if (event.pointerType === 'mouse') setTooltip(null) }}
                    onFocus={(event) => mostrar(item, event.currentTarget)} onBlur={() => setTooltip(null)}
                    onClick={(event) => mostrar(item, event.currentTarget)}
                    onKeyDown={(event) => { if (event.key === 'Escape') setTooltip(null) }}>
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
                  </button>
                </li>
              })}
            </ul>
            <p className="dashboard-classes-note">{referencia ? `Variação vs. referência · ${formatarPeriodo(referencia)}` : 'Participação no consumo total do período'}
              {data.consumo_total_kwh === null ? ' · Participação indisponível: dados incompletos ou inválidos.' : data.consumo_total_kwh === 0 ? ' · Participação indefinida: consumo total zero.' : ''}
            </p>
            {tooltip && detalheTooltip && <div id={tooltipId} role="tooltip" className="dashboard-chart-tooltip dashboard-classes-tooltip" style={{ top: tooltip.top, left: 12 }}>
              <strong>{nomesClasse[detalheTooltip.classe]}</strong>
              <p><span>{formatarPeriodo(periodo)}</span><span>{completo(detalheTooltip.consumo_kwh)}</span></p>
              {referencia && <p><span>Referência · {formatarPeriodo(referencia)}</span><span>{completo(detalheTooltip.consumo_referencia_kwh)}</span></p>}
            </div>}
          </div>}
  </Panel>
}
