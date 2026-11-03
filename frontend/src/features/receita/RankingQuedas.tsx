import { ArrowLeft, TrendingDown } from 'lucide-react'
import { EmptyState } from '../../components/ui/EmptyState'
import { Panel } from '../../components/ui/Panel'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { aprofundar } from './drilldown'
import type { Recorte } from './drilldown'
import { reaisComSinal, variacao } from './formatacao'
import type { AnaliseReceita } from './tipos'

const LIMITE = 8
const nivel = { municipio: 'municípios', bairro: 'bairros', classe: 'classes' }

// Responde ao "se foi volume, quero saber onde": segmentos com maior perda de receita por volume.
export function RankingQuedas({ analise, recorte, onRecorte, onVoltar }: { analise: AnaliseReceita; recorte: Recorte; onRecorte: (r: Recorte) => void; onVoltar?: () => void }) {
  const quedas = analise.linhas.filter((l) => l.efeito_volume < 0).sort((a, b) => a.efeito_volume - b.efeito_volume).slice(0, LIMITE)
  const maior = Math.abs(quedas[0]?.efeito_volume ?? 1)
  return (
    <Panel title="Maiores perdas por volume" description={`Efeito volume dos ${nivel[analise.agrupar_por]} com queda, em R$`}
      className="receita-ranking-panel"
      info={<InfoTipContent resumo="Segmentos com as maiores perdas de receita associadas à queda da energia faturada."
        nota="A perda é estimada ao preço médio da referência de cada segmento." />}>
      {!quedas.length ? <EmptyState icon={TrendingDown} title="Nenhuma perda por volume" description="Nenhum segmento do recorte perdeu receita por volume." compact />
        : <ol className="receita-ranking">
          {quedas.map((linha) => {
            const destino = aprofundar(recorte, linha)
            const conteudo = <>
              <span className="receita-ranking-cabecalho">
                <span className="receita-ranking-nome">{linha.rotulo}{linha.bairro && <small>{linha.municipio}</small>}</span>
                <span className="receita-ranking-valor">{reaisComSinal(linha.efeito_volume)}<small>energia {variacao(linha.variacao_energia_pct)}</small></span>
              </span>
              <span className="receita-ranking-trilho" aria-hidden="true">
                <span className="receita-ranking-barra" style={{ width: `${(Math.abs(linha.efeito_volume) / maior) * 100}%` }} />
              </span>
            </>
            return <li key={linha.chave}>
              {destino ? <button type="button" className="receita-ranking-item" onClick={() => onRecorte(destino)}
                aria-label={`${linha.rotulo}${linha.bairro ? `, ${linha.municipio}` : ''}: efeito volume ${reaisComSinal(linha.efeito_volume)}. Detalhar.`}>{conteudo}</button>
                : <div className="receita-ranking-item">{conteudo}</div>}
            </li>
          })}
        </ol>}
      {onVoltar && <div className="receita-ranking-rodape">
        <button type="button" className="button button--secondary receita-ranking-voltar"
          onClick={onVoltar} aria-label="Voltar ao recorte anterior" title="Voltar">
          <ArrowLeft size={16} aria-hidden="true" />
        </button>
      </div>}
    </Panel>
  )
}
