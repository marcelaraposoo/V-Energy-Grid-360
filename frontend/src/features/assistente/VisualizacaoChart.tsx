import type { Visualizacao } from '../../api'
import '../../components/ui/portal.css'

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })

function formatar(valor: number, unidade?: string | null): string {
  const texto = numero.format(valor)
  if (!unidade) return texto
  if (unidade === 'R$') return `R$ ${texto}`
  if (unidade === '%') return `${texto}%`
  return `${texto} ${unidade}`
}

function Barras({ spec }: { spec: Visualizacao }) {
  const maximo = Math.max(...spec.points.map((p) => Math.abs(p.value)), 0) || 1
  return (
    <ul className="viz-bars">
      {spec.points.map((p) => (
        <li key={p.label}>
          <span className="viz-label" title={p.label}>
            {p.label}
          </span>
          <span className="viz-track" aria-hidden="true">
            <span
              className={`viz-fill${p.value < 0 ? ' viz-fill--neg' : ''}`}
              style={{ width: `${(Math.abs(p.value) / maximo) * 100}%` }}
            />
          </span>
          <span className="viz-value">{formatar(p.value, spec.unit)}</span>
        </li>
      ))}
    </ul>
  )
}

const L = 560
const A = 200
const MARGEM = { e: 12, d: 12, t: 14, b: 28 }

function Linha({ spec }: { spec: Visualizacao }) {
  const pontos = spec.points
  const n = pontos.length
  const valores = pontos.map((p) => p.value)
  const minimo = Math.min(...valores)
  const maximo = Math.max(...valores)
  const folga = (maximo - minimo) * 0.15 || Math.abs(maximo) * 0.1 || 1
  const y0 = minimo - folga
  const y1 = maximo + folga
  const x = (i: number) => MARGEM.e + (n === 1 ? (L - MARGEM.e - MARGEM.d) / 2 : (i / (n - 1)) * (L - MARGEM.e - MARGEM.d))
  const y = (v: number) => MARGEM.t + (1 - (v - y0) / (y1 - y0)) * (A - MARGEM.t - MARGEM.b)
  const caminho = pontos.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')
  return (
    <svg className="viz-line" viewBox={`0 0 ${L} ${A}`} role="img" aria-label={`Gráfico de linha: ${spec.title}`}>
      <line x1={MARGEM.e} x2={L - MARGEM.d} y1={A - MARGEM.b} y2={A - MARGEM.b} stroke="var(--border-subtle)" />
      <path d={caminho} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {pontos.map((p, i) => (
        <circle key={p.label} cx={x(i)} cy={y(p.value)} r="3.5" fill="var(--accent)">
          <title>{`${p.label}: ${formatar(p.value, spec.unit)}`}</title>
        </circle>
      ))}
      <text x={MARGEM.e} y={A - 8} textAnchor="start">
        {pontos[0].label}
      </text>
      {n > 1 && (
        <text x={L - MARGEM.d} y={A - 8} textAnchor="end">
          {pontos[n - 1].label}
        </text>
      )}
    </svg>
  )
}

export function VisualizacaoChart({ spec }: { spec: Visualizacao }) {
  return (
    <figure className="viz">
      <figcaption className="viz-title">{spec.title}</figcaption>
      {spec.type === 'line' ? <Linha spec={spec} /> : <Barras spec={spec} />}
      {(spec.x_label || spec.y_label) && (
        <p className="viz-axes">
          {[spec.x_label, spec.y_label].filter(Boolean).join(' · ')}
        </p>
      )}
      <details className="viz-data">
        <summary>Ver os dados em tabela</summary>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{spec.x_label || 'Item'}</th>
              <th scope="col" className="num">
                {spec.y_label || 'Valor'}
              </th>
            </tr>
          </thead>
          <tbody>
            {spec.points.map((p) => (
              <tr key={p.label}>
                <th scope="row">{p.label}</th>
                <td className="num">{formatar(p.value, spec.unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
