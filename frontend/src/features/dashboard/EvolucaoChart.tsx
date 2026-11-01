import { useId, useRef, useState } from 'react'
import type { Periodo } from '../../api/types'
import { ChartNoAxesCombined } from 'lucide-react'
import { EmptyState } from '../../components/ui/EmptyState'
import { quantidadeMeses } from '../../utils/periodosDashboard'

type EvolucaoChartProps = {
  titulo: string
  atual: number[]
  referencia?: number[]
  periodoAtual: Periodo
  periodoReferencia?: Periodo | null
  unidade: 'R$' | 'kWh'
}

const competencia = new Intl.DateTimeFormat('pt-BR', {
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

function formatarMes(inicio: string, indice: number) {
  const [ano, mes] = inicio.split('-').map(Number)
  return competencia
    .format(new Date(Date.UTC(ano, mes - 1 + indice)))
    .replace(' de ', '/')
    .replace('.', '')
}

function formatarMesCurto(inicio: string, indice: number) {
  return formatarMes(inicio, indice).replace(/\/\d{2}(\d{2})$/, '/$1')
}

export function EvolucaoChart({
  titulo,
  atual,
  referencia = [],
  periodoAtual,
  periodoReferencia,
  unidade,
}: EvolucaoChartProps) {
  const [tooltip, setTooltip] = useState<{
    indice: number
    x: number
    y: number
  } | null>(null)
  const containerRef = useRef<HTMLElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()
  const largura = 600
  const mesesSelecionados = quantidadeMeses(periodoAtual)
  const comparar = Boolean(periodoReferencia && referencia.length === mesesSelecionados
    && quantidadeMeses(periodoReferencia) === mesesSelecionados && atual.length === mesesSelecionados)
  const mesmosMeses = comparar && periodoAtual.inicio.slice(5, 7) === periodoReferencia?.inicio.slice(5, 7)
  const mensal = mesesSelecionados === 1
  const altura = mensal ? 250 : 240
  const esquerda = 38
  const direita = 24
  const topo = 22
  const base = 204
  const rotuloPeriodo = (p: Periodo) => p.inicio === p.fim
    ? formatarMes(p.inicio, 0) : `${formatarMes(p.inicio, 0)} a ${formatarMes(p.fim, 0)}`
  const maximo =
    Math.ceil(Math.max(1, ...atual, ...(comparar ? referencia : [])) / 5_000_000) * 5_000_000
  const espacoMes = (largura - esquerda - direita) / Math.max(atual.length - 1, 1)
  const larguraBarra = 64
  const xAtualMensal = esquerda + (largura - esquerda - direita) * (comparar ? 0.3 : 0.5)
  const xReferenciaMensal = esquerda + (largura - esquerda - direita) * 0.7
  const x = (indice: number) => esquerda + indice * espacoMes
  const y = (valor: number) => base - (valor / maximo) * (base - topo)
  const pontos = (valores: number[]) => valores.map((valor, i) => `${x(i)},${y(valor)}`).join(' ')
  const passoRotulos = !comparar && atual.length > 12 ? Math.ceil(atual.length / 8) : 1
  const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
  const moeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
  const formatarValor = (valor: number) =>
    unidade === 'R$' ? moeda.format(valor) : `${numero.format(valor)} kWh`
  const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 2,
    ...(unidade === 'R$' ? { style: 'currency', currency: 'BRL' } : {}) })
  const valorDaBarra = (valor: number) => `${compacto.format(valor)}${unidade === 'kWh' ? ' kWh' : ''}`

  function mostrarTooltip(indice: number, clientX: number, clientY: number) {
    const container = containerRef.current?.getBoundingClientRect()
    if (!container) return
    const larguraTooltip =
      tooltipRef.current?.offsetWidth ?? Math.min(260, container.width - 24)
    const alturaTooltip = tooltipRef.current?.offsetHeight ?? 70
    const cursorX = clientX - container.left
    const cursorY = clientY - container.top
    const x =
      cursorX + larguraTooltip + 12 > container.width
        ? cursorX - larguraTooltip - 12
        : cursorX + 12
    const y =
      cursorY - alturaTooltip - 12 < 0
        ? cursorY + 12
        : cursorY - alturaTooltip - 12
    setTooltip({
      indice,
      x: Math.max(8, Math.min(x, container.width - larguraTooltip - 8)),
      y: Math.max(8, Math.min(y, container.height - alturaTooltip - 8)),
    })
  }

  function mostrarTooltipDoMes(indice: number, grupo: SVGGElement) {
    const caixa = grupo.getBoundingClientRect()
    mostrarTooltip(indice, caixa.left + caixa.width / 2, caixa.top)
  }

  if (!atual.length || atual.length !== mesesSelecionados) return <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período"
    description="Não há valores mensais disponíveis no intervalo selecionado." compact />
  if (periodoReferencia && !comparar) return <EmptyState icon={ChartNoAxesCombined} title="Sem dados para comparação"
    description={`Não há dados completos para a referência ${rotuloPeriodo(periodoReferencia)}.`} compact />

  return (
    <figure ref={containerRef} className={`dashboard-chart${mensal ? '' : ' dashboard-chart--lines'}`}>
      <div className="dashboard-chart-scroll" onScroll={() => setTooltip(null)}>
        <svg
          viewBox={`0 0 ${largura} ${altura}`}
          role="group"
          aria-roledescription={mensal ? 'gráfico de barras' : 'gráfico de linhas'}
          aria-label={`${titulo}: ${rotuloPeriodo(periodoAtual)}${comparar && periodoReferencia ? `, comparado a ${rotuloPeriodo(periodoReferencia)}` : ''}`}
        >
          {[0, maximo / 2, maximo].map((valor) => (
            <g key={valor}>
              <line
                x1={esquerda}
                x2={largura - direita}
                y1={y(valor)}
                y2={y(valor)}
                className="dashboard-chart-grid"
              />
              <text x={esquerda - 10} y={y(valor) + 4} textAnchor="end">
                {numero.format(valor / 1_000_000)}
              </text>
            </g>
          ))}
          {!mensal && <>
            {comparar && <polyline points={pontos(referencia)} className="dashboard-chart-line dashboard-chart-reference" />}
            <polyline points={pontos(atual)} className="dashboard-chart-line dashboard-chart-current" />
          </>}
          {atual.map((_, indice) => (
            <g key={indice}>
              {mensal ? <>
                <text x={xAtualMensal} y={base + 24} textAnchor="middle" className="dashboard-chart-axis-current">
                  {formatarMes(periodoAtual.inicio, 0)}
                </text>
                {comparar && periodoReferencia && <text x={xReferenciaMensal} y={base + 24} textAnchor="middle" className="dashboard-chart-axis-reference">
                  {formatarMes(periodoReferencia.inicio, 0)}
                </text>}
              </> : (indice % passoRotulos === 0 || indice === atual.length - 1) && (
                <text x={x(indice)} y={altura - 12} textAnchor="middle" className="dashboard-chart-axis">
                  {comparar
                    ? mesmosMeses ? formatarMes(periodoAtual.inicio, indice).split('/')[0] : `Mês ${indice + 1}`
                    : formatarMesCurto(periodoAtual.inicio, indice)}
                </text>
              )}
              <g
                role="button"
                tabIndex={0}
                data-active={tooltip?.indice === indice}
                aria-label={`${titulo}: ${formatarMes(periodoAtual.inicio, indice)}${comparar && periodoReferencia ? `, comparado a ${formatarMes(periodoReferencia.inicio, indice)}` : ''}`}
                aria-describedby={
                  tooltip?.indice === indice ? tooltipId : undefined
                }
                onPointerEnter={(event) => {
                  if (event.pointerType === 'mouse')
                    mostrarTooltip(indice, event.clientX, event.clientY)
                }}
                onPointerMove={(event) => {
                  if (event.pointerType === 'mouse')
                    mostrarTooltip(indice, event.clientX, event.clientY)
                }}
                onPointerLeave={(event) => {
                  if (event.pointerType === 'mouse') setTooltip(null)
                }}
                onFocus={(event) =>
                  mostrarTooltipDoMes(indice, event.currentTarget)
                }
                onBlur={() => setTooltip(null)}
                onClick={(event) =>
                  mostrarTooltip(indice, event.clientX, event.clientY)
                }
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setTooltip(null)
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    mostrarTooltipDoMes(indice, event.currentTarget)
                  }
                }}
              >
                {mensal ? <>
                  <rect x={xAtualMensal - larguraBarra / 2} y={y(atual[0])} width={larguraBarra}
                    height={base - y(atual[0])} rx={2} className="dashboard-chart-current" />
                  <text x={xAtualMensal} y={y(atual[0]) - 8} textAnchor="middle" className="dashboard-chart-bar-value">
                    {valorDaBarra(atual[0])}
                  </text>
                  {comparar && <>
                  <rect x={xReferenciaMensal - larguraBarra / 2} y={y(referencia[0])} width={larguraBarra}
                    height={base - y(referencia[0])} rx={2} className="dashboard-chart-reference" />
                  <text x={xReferenciaMensal} y={y(referencia[0]) - 8} textAnchor="middle" className="dashboard-chart-bar-value">
                    {valorDaBarra(referencia[0])}
                  </text>
                  </>}
                </> : <>
                  {comparar && <circle cx={x(indice)} cy={y(referencia[indice])} r={tooltip?.indice === indice ? 7 : 4}
                    className="dashboard-chart-point dashboard-chart-reference" />}
                  <circle cx={x(indice)} cy={y(atual[indice])} r={tooltip?.indice === indice ? 7 : 4}
                    className="dashboard-chart-point dashboard-chart-current" />
                  {tooltip?.indice === indice && <>
                    {comparar && <circle cx={x(indice)} cy={y(referencia[indice])} r={2.5}
                      className="dashboard-chart-reference" pointerEvents="none" aria-hidden="true" />}
                    <circle cx={x(indice)} cy={y(atual[indice])} r={2.5}
                      className="dashboard-chart-current" pointerEvents="none" aria-hidden="true" />
                  </>}
                </>}
                <rect
                  x={mensal ? esquerda : Math.max(esquerda, x(indice) - espacoMes / 2)}
                  y={topo}
                  width={mensal ? largura - esquerda - direita
                    : Math.min(largura - direita, x(indice) + espacoMes / 2) - Math.max(esquerda, x(indice) - espacoMes / 2)}
                  height={base - topo}
                  fill="transparent"
                />
              </g>
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="dashboard-chart-legend">
        {comparar && periodoReferencia && <span>
          <i className="dashboard-chart-key" />
          {rotuloPeriodo(periodoReferencia)}
        </span>}
        <span>
          <i className="dashboard-chart-key dashboard-chart-key--current" />
          {rotuloPeriodo(periodoAtual)}
        </span>
      </figcaption>
      {tooltip && (
        <div
          ref={tooltipRef}
          id={tooltipId}
          role="tooltip"
          className="dashboard-chart-tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {comparar && periodoReferencia && <p>
            <span>
              {formatarMes(periodoReferencia.inicio, tooltip.indice)}
            </span>
            <span>{formatarValor(referencia[tooltip.indice])}</span>
          </p>}
          <p className="dashboard-chart-tooltip-current">
            <span>{formatarMes(periodoAtual.inicio, tooltip.indice)}</span>
            <strong>{formatarValor(atual[tooltip.indice])}</strong>
          </p>
        </div>
      )}
    </figure>
  )
}
