import { useId, useRef, useState } from 'react'
import { dashboardMock } from './mockData'

type EvolucaoChartProps = {
  titulo: string
  atual: number[]
  referencia: number[]
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

export function EvolucaoChart({
  titulo,
  atual,
  referencia,
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
  const altura = 240
  const esquerda = 38
  const direita = 16
  const topo = 22
  const base = 204
  const maximo =
    Math.ceil(Math.max(...atual, ...referencia) / 5_000_000) * 5_000_000
  const x = (indice: number) =>
    esquerda + (indice * (largura - esquerda - direita)) / (atual.length - 1)
  const y = (valor: number) => base - (valor / maximo) * (base - topo)
  const pontos = (valores: number[]) =>
    valores.map((valor, indice) => `${x(indice)},${y(valor)}`).join(' ')
  const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
  const moeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
  const formatarValor = (valor: number) =>
    unidade === 'R$' ? moeda.format(valor) : `${numero.format(valor)} kWh`

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

  function mostrarTooltipDoPonto(indice: number, grupo: SVGGElement) {
    const caixa = grupo.getBoundingClientRect()
    mostrarTooltip(indice, caixa.left + caixa.width / 2, caixa.top)
  }

  return (
    <figure ref={containerRef} className="dashboard-chart">
      <div className="dashboard-chart-scroll" onScroll={() => setTooltip(null)}>
        <svg
          viewBox={`0 0 ${largura} ${altura}`}
          role="group"
          aria-label={`${titulo}: comparação mensal entre ${dashboardMock.atual.periodo} e ${dashboardMock.referencia.periodo}`}
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
          <polyline
            points={pontos(referencia)}
            className="dashboard-chart-reference"
          />
          <polyline
            points={pontos(atual)}
            className="dashboard-chart-current"
          />
          {dashboardMock.meses.map((mes, indice) => (
            <g key={mes}>
              <text x={x(indice)} y={altura - 12} textAnchor="middle">
                {mes}
              </text>
              <g
                role="button"
                tabIndex={0}
                data-active={tooltip?.indice === indice}
                aria-label={`${titulo}: ${formatarMes(dashboardMock.atual.inicio, indice)}, comparado a ${formatarMes(dashboardMock.referencia.inicio, indice)}`}
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
                  mostrarTooltipDoPonto(indice, event.currentTarget)
                }
                onBlur={() => setTooltip(null)}
                onClick={(event) =>
                  mostrarTooltip(indice, event.clientX, event.clientY)
                }
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setTooltip(null)
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    mostrarTooltipDoPonto(indice, event.currentTarget)
                  }
                }}
              >
                <circle
                  cx={x(indice)}
                  cy={y(referencia[indice])}
                  r={tooltip?.indice === indice ? 7 : 4}
                  className="dashboard-chart-point dashboard-chart-point--reference"
                />
                <circle
                  cx={x(indice)}
                  cy={y(atual[indice])}
                  r={tooltip?.indice === indice ? 7 : 4}
                  className="dashboard-chart-point"
                />
                {[referencia[indice], atual[indice]].map((valor, serie) => (
                  <circle
                    key={serie}
                    cx={x(indice)}
                    cy={y(valor)}
                    r={10}
                    fill="transparent"
                  />
                ))}
              </g>
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="dashboard-chart-legend">
        <span>
          <i className="dashboard-chart-key" />
          {dashboardMock.referencia.periodo}
        </span>
        <span>
          <i className="dashboard-chart-key dashboard-chart-key--current" />
          {dashboardMock.atual.periodo}
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
          <p>
            <span>
              {formatarMes(dashboardMock.referencia.inicio, tooltip.indice)}
            </span>
            <span>{formatarValor(referencia[tooltip.indice])}</span>
          </p>
          <p className="dashboard-chart-tooltip-current">
            <span>{formatarMes(dashboardMock.atual.inicio, tooltip.indice)}</span>
            <strong>{formatarValor(atual[tooltip.indice])}</strong>
          </p>
        </div>
      )}
    </figure>
  )
}
