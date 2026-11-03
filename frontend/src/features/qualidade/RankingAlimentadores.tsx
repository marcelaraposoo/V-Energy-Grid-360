import { useState } from 'react'
import { ArrowDown, ArrowUp, ChevronRight, Info, Table2 } from 'lucide-react'
import type { AlimentadorDecFec, Periodo } from '../../api/types'
import { EmptyState } from '../../components/ui/EmptyState'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { Panel } from '../../components/ui/Panel'
import { formatarCompetencia, formatarPeriodo } from '../dashboard/formatacao'
import { variacao } from '../../utils/indicadores'
import { LIMITE_BASE_PEQUENA, horas, horasImpacto, pct, quantidade, variacaoPct, vezes } from './formatacao'

const LIMITE = 10
type Campo = 'dec_horas' | 'dec_base' | 'fec_vezes' | 'n_ocorrencias' | 'horas_interrompidas'
  | 'qtd_ucs_afetadas' | 'horas_causas_evitaveis' | 'qtd_ucs_alimentador_mes'
type Linha = AlimentadorDecFec & { dec_base: number | null }

const titulos: Record<Campo, string> = {
  dec_horas: 'DEC', dec_base: 'DEC na referência', fec_vezes: 'FEC', n_ocorrencias: 'Interrupções',
  horas_interrompidas: 'Horas sem energia', qtd_ucs_afetadas: 'UCs afetadas', horas_causas_evitaveis: 'Horas evitáveis',
  qtd_ucs_alimentador_mes: 'UCs',
}

const pequena = (a: AlimentadorDecFec) => a.qtd_ucs_alimentador_mes !== null && a.qtd_ucs_alimentador_mes < LIMITE_BASE_PEQUENA

export function RankingAlimentadores({ alimentadores, base, referencia, selecionado, onSelecionar }: {
  alimentadores: AlimentadorDecFec[]
  base: AlimentadorDecFec[] | null
  referencia: Periodo | null
  selecionado: string | null
  onSelecionar: (alimentadorId: string) => void
}) {
  // Maiores valores primeiro: no DEC, os piores. Um segundo clique inverte.
  const [ordem, setOrdem] = useState<{ campo: Campo; crescente: boolean }>({ campo: 'dec_horas', crescente: false })
  const [expandida, setExpandida] = useState(false)
  const comparar = Boolean(referencia && base)
  const decBase = new Map(base?.map((a) => [a.alimentador_id, a.dec_horas]))
  const linhas: Linha[] = alimentadores.map((a) => ({ ...a, dec_base: decBase.get(a.alimentador_id) ?? null }))
  const ordenadas = [...linhas].sort((a, b) => {
    const va = a[ordem.campo]
    const vb = b[ordem.campo]
    if (va === null || vb === null) return va === vb ? 0 : va === null ? 1 : -1
    return (ordem.crescente ? va - vb : vb - va) || a.alimentador_id.localeCompare(b.alimentador_id)
  })
  const visiveis = expandida ? ordenadas : ordenadas.slice(0, LIMITE)
  const competencia = alimentadores.find((a) => a.competencia_base_ucs)?.competencia_base_ucs
  // Aviso de Dados (D08): no DEC, alimentadores pequenos tendem ao topo.
  const topoDec = [...alimentadores].sort((a, b) => b.dec_horas - a.dec_horas).slice(0, LIMITE)
  const pequenasNoTopo = topoDec.filter(pequena).length
  const avisar = ordem.campo === 'dec_horas' && !ordem.crescente && pequenasNoTopo > 0

  const colunas: Campo[] = ['dec_horas', ...(comparar ? ['dec_base' as const] : []), 'fec_vezes', 'n_ocorrencias',
    'horas_interrompidas', 'qtd_ucs_afetadas', 'horas_causas_evitaveis', 'qtd_ucs_alimentador_mes']

  function cabecalho(campo: Campo) {
    const ativa = ordem.campo === campo
    const detalhe = campo === 'dec_base' && referencia ? formatarPeriodo(referencia)
      : campo === 'qtd_ucs_alimentador_mes' && competencia ? `em ${formatarCompetencia(competencia)}` : null
    return <th key={campo} scope="col" className="num" aria-sort={ativa ? (ordem.crescente ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="qualidade-ordenar" onClick={() => setOrdem({ campo, crescente: ativa ? !ordem.crescente : false })}>
        {titulos[campo]}{ativa && (ordem.crescente ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />)}
      </button>
      {detalhe && <small>{detalhe}</small>}
    </th>
  }

  return (
    <Panel title="Ranking dos alimentadores" description="Selecione um alimentador para ver a evolução e as causas dele. Clique nos títulos para ordenar."
      className="qualidade-ranking"
      info={<InfoTipContent resumo="DEC, FEC e impacto de cada alimentador no período analisado." itens={[
        { rotulo: 'Horas sem energia', texto: 'Soma das horas de todas as interrupções (UC × horas). Uma UC que caiu várias vezes conta várias vezes.' },
        { rotulo: 'UCs afetadas', texto: 'UCs distintas com ao menos uma interrupção no período.' },
        { rotulo: 'Horas evitáveis', texto: 'Horas de causas que a manutenção preventiva pode reduzir; entre parênteses, a parte do total.' },
        { rotulo: 'Base pequena', texto: `Menos de ${LIMITE_BASE_PEQUENA} UCs: poucas ocorrências já elevam muito o DEC.` },
      ]} nota="O DEC alto de um alimentador pequeno pode afetar pouca gente. Compare com as UCs afetadas e as horas sem energia antes de priorizar." />}>
      {!ordenadas.length ? <EmptyState icon={Table2} title="Nenhum alimentador" description="Não há alimentadores para o recorte selecionado." compact /> : <>
        {avisar && <p className="qualidade-aviso" role="note">
          <Info size={14} aria-hidden="true" />
          <span><strong>{pequenasNoTopo} dos {topoDec.length}</strong> primeiros por DEC têm menos de {LIMITE_BASE_PEQUENA} UCs.
            Compare com as UCs afetadas e as horas sem energia antes de priorizar.</span>
        </p>}
        <div className="table-wrap">
          <table className="data-table qualidade-tabela">
            <caption className="sr-only">Alimentadores ordenados por {titulos[ordem.campo]}, {ordem.crescente ? 'do menor para o maior' : 'do maior para o menor'}</caption>
            <thead>
              <tr>
                <th scope="col" className="num">#</th>
                <th scope="col">Alimentador</th>
                {colunas.map(cabecalho)}
              </tr>
            </thead>
            <tbody>
              {visiveis.map((a, i) => {
                const ativo = a.alimentador_id === selecionado
                return (
                  <tr key={a.alimentador_id} data-ativo={ativo || undefined}>
                    <td className="num qualidade-posicao">{i + 1}</td>
                    <th scope="row">
                      <button type="button" className="qualidade-tabela-selecionar" aria-pressed={ativo}
                        onClick={() => onSelecionar(a.alimentador_id)}>
                        <span>{a.alimentador_id}<small>{a.municipio}</small></span>
                        <ChevronRight size={14} aria-hidden="true" />
                      </button>
                    </th>
                    <td className="num"><strong>{horas(a.dec_horas)}</strong></td>
                    {comparar && <td className="num qualidade-referencia"
                      title={a.dec_base === null ? undefined : `Variação: ${variacao(variacaoPct(a.dec_horas, a.dec_base))}`}>
                      {a.dec_base === null ? '—' : horas(a.dec_base)}
                    </td>}
                    <td className="num">{vezes(a.fec_vezes)}</td>
                    <td className="num">{quantidade(a.n_ocorrencias)}</td>
                    <td className="num">{horasImpacto(a.horas_interrompidas)}</td>
                    <td className="num">{quantidade(a.qtd_ucs_afetadas)}</td>
                    <td className="num">
                      {horasImpacto(a.horas_causas_evitaveis)}
                      {a.horas_interrompidas > 0 && <small>({pct((100 * a.horas_causas_evitaveis) / a.horas_interrompidas)})</small>}
                    </td>
                    <td className="num">
                      {a.qtd_ucs_alimentador_mes === null ? '—' : quantidade(a.qtd_ucs_alimentador_mes)}
                      {pequena(a) && <span className="badge qualidade-base-pequena" title={`Menos de ${LIMITE_BASE_PEQUENA} UCs`}>base pequena</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {ordenadas.length > LIMITE && <div className="table-footer">
          <span>Exibindo <strong>{visiveis.length}</strong> de <strong>{ordenadas.length}</strong> alimentadores</span>
          <button type="button" className="link-button" onClick={() => setExpandida(!expandida)}>{expandida ? 'Mostrar menos' : 'Mostrar todos'}</button>
        </div>}
      </>}
    </Panel>
  )
}
