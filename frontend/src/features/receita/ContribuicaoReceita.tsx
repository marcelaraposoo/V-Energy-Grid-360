import { useState } from 'react'
import { ArrowDown, ArrowUp, ChevronRight, Table2, X } from 'lucide-react'
import { EmptyState } from '../../components/ui/EmptyState'
import { Panel } from '../../components/ui/Panel'
import { formatarCompetencia } from '../dashboard/formatacao'
import { agrupamentosDisponiveis, aprofundar, filtrar } from './drilldown'
import type { Recorte } from './drilldown'
import { nomesClasse, quantidade, reais, reaisComSinal, tendencia, variacao } from './formatacao'
import type { AgrupamentoReceita, AnaliseReceita, LinhaReceita } from './tipos'

const nomesAgrupamento: Record<AgrupamentoReceita, string> = { municipio: 'Município', bairro: 'Bairro', classe: 'Classe' }
const LIMITE = 10

type Ordem = 'variacao_receita' | 'efeito_volume' | 'efeito_preco' | 'variacao_energia_pct'
const colunasOrdenaveis: { campo: Ordem; titulo: string }[] = [
  { campo: 'variacao_receita', titulo: 'Variação da receita' },
  { campo: 'efeito_volume', titulo: 'Efeito volume' },
  { campo: 'efeito_preco', titulo: 'Efeito preço' },
  { campo: 'variacao_energia_pct', titulo: 'Energia' },
]

type Props = { analise: AnaliseReceita; recorte: Recorte; onRecorte: (recorte: Recorte) => void }

export function ContribuicaoReceita({ analise, recorte, onRecorte }: Props) {
  const [ordem, setOrdem] = useState<{ campo: Ordem; crescente: boolean }>({ campo: 'variacao_receita', crescente: true })
  const [expandida, setExpandida] = useState(false)
  // Piores primeiro por padrão; nulos sempre ao fim.
  const linhas = [...analise.linhas].sort((a, b) => {
    const va = a[ordem.campo]
    const vb = b[ordem.campo]
    if (va === null || vb === null) return va === null ? 1 : -1
    return ordem.crescente ? va - vb : vb - va
  })
  const visiveis = expandida ? linhas : linhas.slice(0, LIMITE)
  const disponiveis = agrupamentosDisponiveis(recorte)

  return (
    <Panel title="Onde a receita mudou" description="Selecione uma linha para detalhar."
      className="receita-contribuicao"
      info="Contribuição de cada segmento para a variação da receita, com a mesma decomposição da ponte. Detalhamento: município → bairro → classe. UCs: faturadas na última competência do período atual."
      actions={disponiveis.length > 1 ? <div className="segmented" role="group" aria-label="Ver por">
        {disponiveis.map((a) => (
          <button key={a} type="button" className="button button--secondary" aria-pressed={recorte.agrupar_por === a}
            onClick={() => onRecorte({ ...recorte, agrupar_por: a })}>{nomesAgrupamento[a]}</button>
        ))}
      </div> : undefined}>
      <div className="receita-trilha">
        <nav aria-label="Nível do detalhamento">
          <ol>
            <li>{recorte.municipio
              ? <button type="button" className="link-button" onClick={() => onRecorte(filtrar(recorte, { municipio: null }))}>Todos os municípios</button>
              : <span aria-current="page">Todos os municípios</span>}</li>
            {recorte.municipio && <li><ChevronRight size={13} aria-hidden="true" />{recorte.bairro
              ? <button type="button" className="link-button" onClick={() => onRecorte(filtrar(recorte, { bairro: null }))}>{recorte.municipio}</button>
              : <span aria-current="page">{recorte.municipio}</span>}</li>}
            {recorte.bairro && <li><ChevronRight size={13} aria-hidden="true" /><span aria-current="page">{recorte.bairro}</span></li>}
          </ol>
        </nav>
        {recorte.classe && <span className="badge receita-chip">
          Classe: {nomesClasse[recorte.classe]}
          <button type="button" aria-label="Remover filtro de classe" onClick={() => onRecorte(filtrar(recorte, { classe: null }))}><X size={12} aria-hidden="true" /></button>
        </span>}
      </div>
      {!linhas.length ? <EmptyState icon={Table2} title="Sem segmentos no recorte" description="Não há faturamento para os filtros selecionados." compact /> : <>
        <div className="table-wrap">
          <table className="data-table receita-tabela">
            <caption className="sr-only">Variação da receita por {nomesAgrupamento[analise.agrupar_por].toLowerCase()}, ordenada por {colunasOrdenaveis.find((c) => c.campo === ordem.campo)?.titulo.toLowerCase()}</caption>
            <thead>
              <tr>
                <th scope="col">{nomesAgrupamento[analise.agrupar_por]}</th>
                <th scope="col" className="num">Receita referência</th>
                <th scope="col" className="num">Receita atual</th>
                {colunasOrdenaveis.map(({ campo, titulo }) => {
                  const ativa = ordem.campo === campo
                  return <th key={campo} scope="col" className="num" aria-sort={ativa ? (ordem.crescente ? 'ascending' : 'descending') : 'none'}>
                    <button type="button" className="receita-ordenar" onClick={() => setOrdem({ campo, crescente: ativa ? !ordem.crescente : true })}>
                      {titulo}{ativa && (ordem.crescente ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
                    </button>
                  </th>
                })}
                <th scope="col" className="num" title="UCs faturadas na última competência do período atual">UCs em {formatarCompetencia(analise.periodo_atual.fim)}</th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((linha) => <Linha key={linha.chave} linha={linha} destino={aprofundar(recorte, linha)} onRecorte={onRecorte} />)}
            </tbody>
            <tfoot>
              <Linha linha={analise.total} destino={null} onRecorte={onRecorte} total />
            </tfoot>
          </table>
        </div>
        {linhas.length > LIMITE && <div className="table-footer">
          <span>Exibindo <strong>{visiveis.length}</strong> de <strong>{linhas.length}</strong> segmentos</span>
          <button type="button" className="link-button" onClick={() => setExpandida(!expandida)}>{expandida ? 'Mostrar menos' : 'Mostrar todos'}</button>
        </div>}
      </>}
    </Panel>
  )
}

function Linha({ linha, destino, onRecorte, total }: { linha: LinhaReceita; destino: Recorte | null; onRecorte: (r: Recorte) => void; total?: boolean }) {
  const rotulo = <>
    <span className="receita-tabela-rotulo">{linha.rotulo}</span>
    {linha.bairro && !total && <small>{linha.municipio}</small>}
  </>
  return (
    <tr className={total ? 'receita-tabela-total' : undefined}>
      <th scope="row">
        {destino ? <button type="button" className="receita-tabela-detalhar" onClick={() => onRecorte(destino)}
          aria-label={`Detalhar ${linha.rotulo}${linha.bairro ? `, ${linha.municipio}` : ''}`}>
          <span>{rotulo}</span><ChevronRight size={14} aria-hidden="true" />
        </button> : <span className="receita-tabela-celula">{rotulo}</span>}
      </th>
      <td className="num">{reais(linha.receita_base)}</td>
      <td className="num">{reais(linha.receita_atual)}</td>
      <td className="num" data-tendencia={tendencia(linha.variacao_receita)}>
        {reaisComSinal(linha.variacao_receita)}<small>{variacao(linha.variacao_receita_pct)}</small>
      </td>
      <td className="num" data-tendencia={tendencia(linha.efeito_volume)}>{reaisComSinal(linha.efeito_volume)}</td>
      <td className="num">{reaisComSinal(linha.efeito_preco)}</td>
      <td className="num" data-tendencia={tendencia(linha.variacao_energia_pct)}>{variacao(linha.variacao_energia_pct)}</td>
      <td className="num">{quantidade(linha.qtd_ucs_atual)}</td>
    </tr>
  )
}
