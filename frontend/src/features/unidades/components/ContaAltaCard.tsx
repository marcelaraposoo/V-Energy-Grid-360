import { CircleHelp } from 'lucide-react'
import {
  formatarCompetencia,
  formatarMoeda,
  formatarNumero,
  formatarPercentual,
} from '../formatters'
import type {
  ClassificacaoVariacao,
  DiagnosticoContaAltaUC,
  TipoComparacaoContaAlta,
} from '../types'
import { UnidadeFields } from './UnidadeFields'

const opcoes: { value: TipoComparacaoContaAlta; label: string }[] = [
  { value: 'mes_anterior', label: 'Mês atual × mês anterior' },
  { value: 'ano_anterior', label: 'Mês atual × mesmo mês do ano anterior' },
  {
    value: 'trimestre_ano_anterior',
    label: 'Últimos 3 meses × mesmo período do ano anterior',
  },
]

const classificacoes: Record<ClassificacaoVariacao, string> = {
  pequena: 'Variação pequena',
  moderada: 'Variação moderada',
  significativa: 'Variação significativa',
  reducao: 'Redução',
}

type ContaAltaCardProps = {
  diagnostico: DiagnosticoContaAltaUC
  comparacao: TipoComparacaoContaAlta
  onComparacaoChange: (value: TipoComparacaoContaAlta) => void
  carregando: boolean
  erro: string | null
  onRetry: () => void
}

export function ContaAltaCard({
  diagnostico,
  comparacao,
  onComparacaoChange,
  carregando,
  erro,
  onRetry,
}: ContaAltaCardProps) {
  return (
    <section
      className="panel ucv-conta-alta"
      aria-labelledby="ucv-conta-alta-title"
    >
      <header>
        <CircleHelp size={20} strokeWidth={1.6} aria-hidden="true" />
        <h2 id="ucv-conta-alta-title">A conta veio alta?</h2>
      </header>
      <p>
        Compare a energia utilizada com o valor cobrado. O mês atual corresponde
        à última competência disponível na base.
      </p>
      <label className="ucv-comparison-label" htmlFor="ucv-comparison">
        Tipo de comparação
      </label>
      <select
        id="ucv-comparison"
        className="ucv-comparison-select"
        value={comparacao}
        onChange={(event) =>
          onComparacaoChange(event.target.value as TipoComparacaoContaAlta)
        }
      >
        {opcoes.map(({ value, label }) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <div
        aria-busy={carregando}
        aria-live="polite"
        className="ucv-diagnostic-result"
      >
        {carregando ? (
          <p role="status">Atualizando comparação…</p>
        ) : erro ? (
          <div role="alert" className="ucv-diagnostic-error">
            <p>{erro}</p>
            <button
              type="button"
              className="button button--secondary"
              onClick={onRetry}
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <>
            <UnidadeFields
              fields={[
                {
                  label: 'Competências atuais',
                  value:
                    diagnostico.competencias_atuais
                      .map(formatarCompetencia)
                      .join(' · ') || 'Não disponíveis',
                },
                {
                  label: 'Competências de referência',
                  value:
                    diagnostico.competencias_referencia
                      .map(formatarCompetencia)
                      .join(' · ') || 'Não disponíveis',
                },
              ]}
            />
            {(
              [
                {
                  key: 'consumo',
                  label: 'Consumo (kWh)',
                  formatar: formatarNumero,
                },
                {
                  key: 'faturamento',
                  label: 'Valor cobrado (R$)',
                  formatar: formatarMoeda,
                },
              ] as const
            ).map(({ key, label, formatar }) => {
              const metrica = diagnostico[key]
              return (
                <section
                  className="ucv-diagnostic-metric"
                  key={key}
                  aria-label={label}
                >
                  <h3>{label}</h3>
                  <p className="ucv-diagnostic-percentage">
                    {formatarPercentual(metrica.variacao_pct)}
                  </p>
                  <span
                    className={`badge ucv-variation${metrica.classificacao ? ` ucv-variation--${metrica.classificacao}` : ''}`}
                  >
                    {metrica.classificacao
                      ? classificacoes[metrica.classificacao]
                      : 'Comparação indisponível'}
                  </span>
                  <UnidadeFields
                    fields={[
                      {
                        label: 'Referência',
                        value: formatar(metrica.valor_referencia),
                      },
                      { label: 'Atual', value: formatar(metrica.valor_atual) },
                    ]}
                  />
                </section>
              )
            })}
          </>
        )}
      </div>
    </section>
  )
}
