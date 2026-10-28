import { formatarCompetencia } from '../formatters'
import type { PeriodoHistorico, PeriodoHistoricoUC } from '../types'

const periodos: { value: PeriodoHistorico; label: string }[] = [
  { value: '6_meses', label: '6 meses' },
  { value: '12_meses', label: '12 meses' },
  { value: 'todos', label: 'Todos' },
]

type FiltroPeriodoHistoricoProps = {
  title: string
  value: PeriodoHistorico
  onChange: (value: PeriodoHistorico) => void
  periodo: PeriodoHistoricoUC
  carregando: boolean
  erro: string | null
}

export function FiltroPeriodoHistorico({
  title,
  value,
  onChange,
  periodo,
  carregando,
  erro,
}: FiltroPeriodoHistoricoProps) {
  const descricao =
    periodo.periodo_inicio && periodo.periodo_fim
      ? `${formatarCompetencia(periodo.periodo_inicio)} a ${formatarCompetencia(periodo.periodo_fim)}`
      : 'Período não disponível'

  return (
    <section className="ucv-history-filter" aria-label={title}>
      <div>
        <h2>{title}</h2>
        <p>
          {carregando
            ? 'Atualizando período…'
            : erro
              ? 'Não foi possível atualizar o período.'
              : descricao}
        </p>
      </div>
      <div className="ucv-history-periods" role="group" aria-label={title}>
        {periodos.map(({ value: periodo, label }) => (
          <button
            key={periodo}
            type="button"
            className="button button--secondary"
            aria-pressed={value === periodo}
            onClick={() => {
              if (value !== periodo) onChange(periodo)
            }}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}
