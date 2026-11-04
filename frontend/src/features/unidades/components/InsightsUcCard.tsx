import { Info, Sparkles, TriangleAlert } from 'lucide-react'
import { api, useApi } from '../../../api'
import { LoadingState } from '../../../components/ui/Feedback'
import { InfoTipContent } from '../../../components/ui/InfoTip'
import { Panel } from '../../../components/ui/Panel'
import { competenciasInsights } from '../insights'
import '../../../components/ui/portal.css'

const icones = { destaque: Sparkles, alerta: TriangleAlert, informativo: Info }

// Leitura automática da UC: responde ao "a conta veio alta?" (consumo × valor cobrado) e soma troca de
// medidor e interrupções. Os números saem da própria Visão 360; a IA, quando ligada, só reescreve o texto.
export function InsightsUcCard({ ucId, competencias }: { ucId: string; competencias: string[] }) {
  const { params, descricao } = competenciasInsights(competencias)
  const { data, error, loading, reload } = useApi(
    (signal) => api.ia.insightsUc(ucId, params, signal),
    [ucId, params.competencia_atual, params.competencia_referencia],
  )

  return (
    <Panel title="Insights da IA" icone={Sparkles} description={descricao} className="ucv-insights"
      info={<InfoTipContent resumo="Leitura automática desta unidade: só aparecem os pontos que se aplicam a ela." itens={[
        { rotulo: 'Conta', texto: 'De onde veio a variação da energia em relação ao mesmo mês do ano anterior: do consumo ou do preço do kWh (e da bandeira).' },
        { rotulo: 'Padrão', texto: 'Se o consumo do mês está em linha com a média dos 6 meses anteriores ou se a variação é sazonal (parecida com a do ano anterior).' },
        { rotulo: 'Rede', texto: 'Troca de medidor nos meses comparados e interrupções dos últimos 12 meses.' },
      ]} nota="Os valores vêm dos dados do portal; a IA só reescreve as frases e não pode citar número que não esteja neles." />}>
      {loading ? <LoadingState label="Gerando insights…" />
        : error ? <p className="insights-note">
          Não foi possível gerar os insights agora.{' '}
          <button type="button" className="link-button" onClick={reload}>Tentar novamente</button>
        </p>
          : !data?.length ? <p className="insights-note">Não há histórico suficiente para gerar insights desta unidade.</p>
            : <>
              <ul className="insights">
                {data.map((insight) => {
                  const Icone = icones[insight.tipo]
                  return <li key={`${insight.tipo}-${insight.texto}`} className={`insight insight--${insight.tipo}`}>
                    <Icone size={16} aria-hidden="true" />
                    <span>{insight.texto}</span>
                  </li>
                })}
              </ul>
              <p className="insights-note">Os valores citados são calculados diretamente dos dados do portal.</p>
            </>}
    </Panel>
  )
}
