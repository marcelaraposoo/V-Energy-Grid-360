import { ChartColumn } from 'lucide-react'
import { EmptyState } from '../../../components/ui/EmptyState'
import { formatarCompetencia, formatarNumero } from '../formatters'
import type { ConsumoMensalUC } from '../types'

export function ConsumoChart({ consumo }: { consumo: ConsumoMensalUC[] }) {
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
        c.consumo_kwh_ano_anterior ?? 0,
      ]),
    ) * 1.1
  const passo = (largura - esquerda - 16) / consumo.length
  const barra = Math.min(16, passo * 0.3)

  return (
    <>
      <div className="ucv-chart-scroll">
        <svg
          className="ucv-chart"
          viewBox={`0 0 ${largura} ${altura}`}
          role="img"
          aria-label="Histórico de consumo mensal em kWh, comparado ao mesmo mês do ano anterior"
        >
          <title>Consumo dos últimos meses disponíveis e do ano anterior</title>
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
              <g key={c.competencia}>
                <rect
                  x={x - barra - 2}
                  y={base - atual}
                  width={barra}
                  height={atual}
                  className="ucv-chart-current"
                >
                  <title>
                    {formatarCompetencia(c.competencia)}:{' '}
                    {formatarNumero(c.consumo_kwh)} kWh
                  </title>
                </rect>
                {c.consumo_kwh_ano_anterior !== null && (
                  <rect
                    x={x + 2}
                    y={base - anterior}
                    width={barra}
                    height={anterior}
                    className="ucv-chart-previous"
                  >
                    <title>
                      Mesmo mês do ano anterior:{' '}
                      {formatarNumero(c.consumo_kwh_ano_anterior)} kWh
                    </title>
                  </rect>
                )}
                <text x={x} y={altura - 16} textAnchor="middle">
                  {formatarCompetencia(c.competencia)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="ucv-chart-legend">
        <span>
          <i className="ucv-legend-dot ucv-legend-dot--accent" />
          Consumo mensal
        </span>
        <span>
          <i className="ucv-legend-dot" />
          Mesmo mês do ano anterior
        </span>
      </div>
      <details className="ucv-chart-values">
        <summary>Ver valores do gráfico</summary>
        <div
          className="ucv-table-scroll"
          tabIndex={0}
          role="region"
          aria-label="Valores do histórico de consumo"
        >
          <table className="ucv-table">
            <caption className="sr-only">Consumo mensal em kWh</caption>
            <thead>
              <tr>
                <th scope="col">Competência</th>
                <th scope="col">Consumo (kWh)</th>
                <th scope="col">Ano anterior (kWh)</th>
              </tr>
            </thead>
            <tbody>
              {consumo.map((c) => (
                <tr key={c.competencia}>
                  <th scope="row">{formatarCompetencia(c.competencia)}</th>
                  <td>{formatarNumero(c.consumo_kwh)}</td>
                  <td>{formatarNumero(c.consumo_kwh_ano_anterior)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}
