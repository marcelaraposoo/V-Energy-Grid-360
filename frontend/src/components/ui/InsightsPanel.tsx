import { Info, Sparkles, TriangleAlert } from 'lucide-react'
import { api, useApi } from '../../api'
import type { InsightsParams, TelaInsight } from '../../api'
import { Panel } from './Panel'
import { LoadingState } from './Feedback'
import './portal.css'

const icones = {
  destaque: Sparkles,
  alerta: TriangleAlert,
  informativo: Info,
}

type InsightsPanelProps = {
  tela: TelaInsight
  titulo?: string
  descricao?: string
  // Filtros enviados ao backend; quando mudam, os insights são recalculados.
  params?: InsightsParams
  // Outros valores que, ao mudar, recalculam os insights (ex.: o total da fila depois de criar uma ordem).
  deps?: readonly unknown[]
}

// Insights gerados pelo backend a partir dos próprios dados da tela. Se a API não tiver insights para a
// tela (lista vazia) ou falhar, o painel some/fica discreto: o insight nunca deve atrapalhar a análise.
export function InsightsPanel({
  tela,
  titulo = 'Insights da IA',
  descricao = 'Leitura automática dos dados desta tela',
  params = {},
  deps = [],
}: InsightsPanelProps) {
  const { data, error, loading, reload } = useApi(
    (signal) => api.ia.insights(tela, params, signal),
    [tela, JSON.stringify(params), ...deps],
  )

  if (!loading && !error && (!data || data.length === 0)) return null

  return (
    <Panel title={titulo} description={descricao}>
      {loading && <LoadingState label="Gerando insights…" />}
      {error && (
        <p className="insights-note">
          Não foi possível gerar os insights agora.{' '}
          <button type="button" className="link-button" onClick={reload}>
            Tentar novamente
          </button>
        </p>
      )}
      {data && data.length > 0 && (
        <>
          <ul className="insights">
            {data.map((insight) => {
              const Icone = icones[insight.tipo]
              return (
                <li key={`${insight.tipo}-${insight.texto}`} className={`insight insight--${insight.tipo}`}>
                  <Icone size={16} aria-hidden="true" />
                  <span>{insight.texto}</span>
                </li>
              )
            })}
          </ul>
          <p className="insights-note">
            Os valores citados são calculados diretamente dos dados do portal.
          </p>
        </>
      )}
    </Panel>
  )
}
