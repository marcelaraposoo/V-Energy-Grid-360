import { CircleSlash } from 'lucide-react'
import type { CausaContinuidade } from '../../api/types'
import { EmptyState } from '../../components/ui/EmptyState'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { Panel } from '../../components/ui/Panel'
import { horasImpacto, nomeCausa, pct, quantidade } from './formatacao'

// Responde ao "onde priorizar manutenção": quanto das horas sem energia vem de causas evitáveis.
export function CausasQualidade({ causas }: { causas: CausaContinuidade[] }) {
  const maior = causas[0]?.horas || 1
  const evitaveis = causas.filter((c) => c.causa_evitavel).reduce((soma, c) => soma + (c.pct_horas ?? 0), 0)
  return (
    <Panel title="Principais causas" description="Horas sem energia por causa, no período analisado" className="qualidade-causas"
      info={<InfoTipContent resumo="Soma das horas sem energia das ocorrências de cada causa." itens={[
        { rotulo: 'Evitável', texto: 'Causa que a manutenção preventiva pode reduzir, conforme a origem dos dados.' },
      ]} nota="Ocorrências sem causa registrada aparecem como “Não informada”." />}>
      {!causas.length ? <EmptyState icon={CircleSlash} title="Nenhuma interrupção" description="Não há ocorrências no recorte selecionado." compact />
        : <>
          <p className="qualidade-causas-destaque">
            <strong>{pct(evitaveis)}</strong> das horas sem energia vieram de causas evitáveis.
          </p>
          <ol className="qualidade-barras">
            {causas.map((c) => (
              <li key={`${c.causa}-${c.causa_evitavel}`} className="qualidade-barra-item">
                <span className="qualidade-barra-cabecalho">
                  <span className="qualidade-barra-nome">
                    {nomeCausa(c.causa)}
                    {c.causa_evitavel && <span className="badge qualidade-evitavel">Evitável</span>}
                  </span>
                  <span className="qualidade-barra-valor">
                    {horasImpacto(c.horas)}<small>{c.pct_horas === null ? '' : pct(c.pct_horas)} · {quantidade(c.qtd_interrupcoes)} ocorrências</small>
                  </span>
                </span>
                <span className="qualidade-barra-trilho" aria-hidden="true">
                  <span className="qualidade-barra" data-evitavel={c.causa_evitavel} style={{ width: `${(c.horas / maior) * 100}%` }} />
                </span>
              </li>
            ))}
          </ol>
        </>}
    </Panel>
  )
}
