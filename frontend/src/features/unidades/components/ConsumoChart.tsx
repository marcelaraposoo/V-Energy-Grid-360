import { useId, useRef, useState } from 'react'
import { ChartColumn } from 'lucide-react'
import { EmptyState } from '../../../components/ui/EmptyState'
import { formatarCompetencia, formatarNumero } from '../formatters'
import type { ConsumoMensalUC } from '../types'

export function ConsumoChart({ consumo }: { consumo: ConsumoMensalUC[] }) {
  const [mostrarAnterior, setMostrarAnterior] = useState(true)
  const [tooltip, setTooltip] = useState<{
    indice: number
    x: number
    y: number
  } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const tooltipId = useId()
  if (!consumo.length) {
    return (
      <EmptyState
        icon={ChartColumn}
        title="Sem histórico de consumo"
        description="Não há leituras disponíveis para esta unidade."
      />
    )
  }

  const largura = 800
  const altura = 280
  const esquerda = 64
  const topo = 20
  const base = altura - 40
  const amplitude = base - topo
  const maximo =
    Math.max(
      1,
      ...consumo.flatMap((c) => [
        c.consumo_kwh,
        mostrarAnterior ? (c.consumo_kwh_ano_anterior ?? 0) : 0,
      ]),
    ) * 1.1
  const passo = (largura - esquerda - 16) / consumo.length
  const barra = Math.min(16, passo * 0.3)
  const selecionado = tooltip === null ? undefined : consumo[tooltip.indice]

  function mostrarTooltip(indice: number, clientX: number, clientY: number) {
    const container = containerRef.current?.getBoundingClientRect()
    if (!container) return
    const larguraTooltip =
      tooltipRef.current?.offsetWidth ?? Math.min(200, container.width - 24)
    const alturaTooltip = tooltipRef.current?.offsetHeight ?? 100
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

  function mostrarTooltipDoGrupo(indice: number, grupo: SVGGElement) {
    const caixa = grupo.getBoundingClientRect()
    mostrarTooltip(
      indice,
      caixa.left + caixa.width / 2,
      caixa.top + caixa.height / 2,
    )
  }

  return (
    <>
      <label className="ucv-chart-comparison">
        <input
          type="checkbox"
          checked={mostrarAnterior}
          onChange={(event) => {
            setMostrarAnterior(event.target.checked)
            setTooltip(null)
          }}
        />
        Comparar com o mesmo mês do ano anterior
      </label>
      <div ref={containerRef} className="ucv-chart-container">
        <div className="ucv-chart-scroll" onScroll={() => setTooltip(null)}>
          <svg
            className="ucv-chart"
            viewBox={`0 0 ${largura} ${altura}`}
            role="group"
            aria-label={
              mostrarAnterior
                ? 'Histórico de consumo mensal em kWh, comparado ao mesmo mês do ano anterior'
                : 'Histórico de consumo mensal em kWh'
            }
          >
            {[0, 1, 2, 3, 4].map((i) => {
              const valor = (maximo * i) / 4
              const y = base - (amplitude * i) / 4
              return (
                <g key={i}>
                  <line
                    x1={esquerda}
                    x2={largura - 16}
                    y1={y}
                    y2={y}
                    className="ucv-chart-grid"
                  />
                  <text x={esquerda - 8} y={y + 4} textAnchor="end">
                    {formatarNumero(valor)}
                  </text>
                </g>
              )
            })}
            {consumo.map((c, i) => {
              const x = esquerda + passo * (i + 0.5)
              const atual = (c.consumo_kwh / maximo) * amplitude
              const anterior =
                ((c.consumo_kwh_ano_anterior ?? 0) / maximo) * amplitude
              return (
                <g
                  key={c.competencia}
                  role="button"
                  tabIndex={0}
                  aria-label={`Consumo de ${formatarCompetencia(c.competencia)}${mostrarAnterior ? ' comparado ao mesmo mês do ano anterior' : ''}`}
                  aria-describedby={
                    tooltip?.indice === i ? tooltipId : undefined
                  }
                  onPointerEnter={(event) => {
                    if (event.pointerType === 'mouse')
                      mostrarTooltip(i, event.clientX, event.clientY)
                  }}
                  onPointerMove={(event) => {
                    if (event.pointerType === 'mouse')
                      mostrarTooltip(i, event.clientX, event.clientY)
                  }}
                  onPointerLeave={(event) => {
                    if (event.pointerType === 'mouse') setTooltip(null)
                  }}
                  onFocus={(event) =>
                    mostrarTooltipDoGrupo(i, event.currentTarget)
                  }
                  onBlur={() => setTooltip(null)}
                  onClick={(event) =>
                    mostrarTooltip(i, event.clientX, event.clientY)
                  }
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') setTooltip(null)
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      mostrarTooltipDoGrupo(i, event.currentTarget)
                    }
                  }}
                >
                  <rect
                    x={esquerda + passo * i}
                    y={topo}
                    width={passo}
                    height={base - topo + 24}
                    fill="transparent"
                  />
                  {mostrarAnterior && c.consumo_kwh_ano_anterior !== null && (
                    <rect
                      x={x - barra - 2}
                      y={base - anterior}
                      width={barra}
                      height={anterior}
                      className="ucv-chart-previous"
                    />
                  )}
                  <rect
                    x={mostrarAnterior ? x + 2 : x - barra / 2}
                    y={base - atual}
                    width={barra}
                    height={atual}
                    className="ucv-chart-current"
                  />
                  <text x={x} y={altura - 16} textAnchor="middle">
                    {formatarCompetencia(c.competencia)}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
        {selecionado && tooltip && (
          <div
            ref={tooltipRef}
            id={tooltipId}
            role="tooltip"
            className="ucv-chart-tooltip"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            <p>{formatarCompetencia(selecionado.competencia)}</p>
            {mostrarAnterior && (
              <p>
                <span>{Number(selecionado.competencia.slice(0, 4)) - 1}</span>
                <span>
                  {selecionado.consumo_kwh_ano_anterior === null
                    ? 'Não disponível'
                    : `${formatarNumero(selecionado.consumo_kwh_ano_anterior)} kWh`}
                </span>
              </p>
            )}
            <p className="ucv-chart-tooltip-current">
              <span>{selecionado.competencia.slice(0, 4)}</span>
              <strong>{formatarNumero(selecionado.consumo_kwh)} kWh</strong>
            </p>
          </div>
        )}
      </div>
      <div className="ucv-chart-legend">
        {mostrarAnterior && (
          <span>
            <i className="ucv-legend-dot" />
            Referência (ano anterior)
          </span>
        )}
        <span>
          <i className="ucv-legend-dot ucv-legend-dot--accent" />
          Atual
        </span>
      </div>
    </>
  )
}
