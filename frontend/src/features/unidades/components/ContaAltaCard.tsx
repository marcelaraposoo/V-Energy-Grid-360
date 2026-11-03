import { CircleHelp } from 'lucide-react'
import { InfoTip, InfoTipContent } from '../../../components/ui/InfoTip'
import {
  formatarCompetencia,
  formatarMoeda,
  formatarNumero,
  formatarPercentual,
} from '../formatters'
import type {
  ClassificacaoVariacao,
  DiagnosticoContaAltaUC,
  SelecaoContaAlta,
} from '../types'
import { UnidadeFields } from './UnidadeFields'
import { SeletorCompetencia } from './SeletorCompetencia'

const classificacoes: Record<ClassificacaoVariacao, string> = {
  pequena: 'Variação pequena',
  moderada: 'Variação moderada',
  significativa: 'Variação significativa',
  reducao: 'Redução',
}

type ContaAltaCardProps = {
  diagnostico: DiagnosticoContaAltaUC
  comparacao: SelecaoContaAlta
  onComparacaoChange: (value: SelecaoContaAlta) => void
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
  const competencias = diagnostico.competencias_disponiveis
  const referencias = competencias.filter(
    (c) =>
      comparacao.competencia_atual !== null && c < comparacao.competencia_atual,
  )
  return (
    <section
      className="panel ucv-conta-alta"
      aria-labelledby="ucv-conta-alta-title"
    >
      <header>
        <CircleHelp size={20} strokeWidth={1.6} aria-hidden="true" />
        <h2 id="ucv-conta-alta-title">A conta veio alta?</h2>
        <InfoTip titulo="Como comparar a conta">
          <InfoTipContent resumo="Escolha dois meses para separar a mudança no consumo da mudança no valor cobrado." itens={[
            { rotulo: 'Consumo', texto: 'Compara a energia faturada, em kWh.' },
            { rotulo: 'Valor cobrado', texto: 'Compara o total da fatura, incluindo tributos.' },
          ]} nota="Uma conta maior não significa, necessariamente, mais consumo. Sem referência válida, a variação fica indisponível." />
        </InfoTip>
      </header>
      <p>
        Compare a energia utilizada com o valor cobrado nos meses com histórico
        desta unidade.
      </p>
      <SeletorCompetencia
        label="Mês analisado"
        valor={comparacao.competencia_atual}
        competencias={competencias}
        vazio="Sem histórico disponível"
        onChange={(competencia) => {
          const anteriores = competencias.filter((c) => c < competencia)
          onComparacaoChange({
            competencia_atual: competencia,
            competencia_referencia:
              comparacao.competencia_referencia &&
              comparacao.competencia_referencia < competencia
                ? comparacao.competencia_referencia
                : (anteriores.at(-1) ?? null),
          })
        }}
      />
      <SeletorCompetencia
        label="Mês de referência"
        valor={comparacao.competencia_referencia}
        competencias={referencias}
        vazio="Sem mês anterior disponível"
        onChange={(competencia) =>
          onComparacaoChange({
            ...comparacao,
            competencia_referencia: competencia,
          })
        }
      />
      <span className="sr-only" role="status">
        {carregando ? 'Atualizando comparação…' : ''}
      </span>
      <div
        aria-busy={carregando}
        aria-live="polite"
        className="ucv-diagnostic-result"
      >
        {erro ? (
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
            {(diagnostico.troca_medidor_atual || diagnostico.troca_medidor_referencia) && (
              <p className="ucv-troca-note">
                Troca de medidor em{' '}
                {[
                  diagnostico.troca_medidor_referencia && diagnostico.competencia_referencia
                    ? `${formatarCompetencia(diagnostico.competencia_referencia)} (referência)` : null,
                  diagnostico.troca_medidor_atual && diagnostico.competencia_atual
                    ? `${formatarCompetencia(diagnostico.competencia_atual)} (mês analisado)` : null,
                ].filter(Boolean).join(' e ')}.
                {' '}No mês da troca, o consumo usa a leitura atual do medidor novo.
              </p>
            )}
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
                  {metrica.variacao_pct === null && (
                    <p className="ucv-diagnostic-unavailable">
                      {metrica.mensagem}
                    </p>
                  )}
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
