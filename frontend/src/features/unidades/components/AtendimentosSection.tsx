import { useState } from 'react'
import { ChevronLeft, ChevronRight, Headphones } from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { InfoTipContent } from '../../../components/ui/InfoTip'
import { EmptyState } from '../../../components/ui/EmptyState'
import { formatarData, formatarNumero } from '../formatters'
import type { AtendimentoUC, Visao360 } from '../types'
import { HistoryTable } from './HistoryTable'
import { AtendimentoDialog } from './AtendimentoDialog'

const situacoes = [
  { id: 'todos', label: 'Todos', vazio: 'Não há chamados registrados para esta unidade.' },
  { id: 'abertos', label: 'Abertos', vazio: 'Não há chamados abertos para esta unidade.' },
  { id: 'fechados', label: 'Fechados', vazio: 'Não há chamados fechados para esta unidade.' },
] as const
const tamanhoPagina = 10

export function AtendimentosSection({ dados }: { dados: Visao360 }) {
  const [situacao, setSituacao] = useState<typeof situacoes[number]['id']>('todos')
  const [pagina, setPagina] = useState(1)
  const [atendimento, setAtendimento] = useState<AtendimentoUC | null>(null)
  const todos = dados.atendimentos
  const abertos = todos.filter(item => item.aberto).length
  const quantidades = { todos: todos.length, abertos, fechados: todos.length - abertos }
  const filtrados = todos
    .filter(item => situacao === 'todos' || item.aberto === (situacao === 'abertos'))
    .sort((a, b) => b.data.localeCompare(a.data) || b.protocolo.localeCompare(a.protocolo))
  const paginas = Math.max(1, Math.ceil(filtrados.length / tamanhoPagina))
  const paginaAtual = Math.min(pagina, paginas)
  const itens = filtrados.slice((paginaAtual - 1) * tamanhoPagina, paginaAtual * tamanhoPagina)
  const vazio = situacoes.find(item => item.id === situacao)!.vazio

  return (
    <Panel title="Chamados de atendimento" description="Histórico completo da unidade" className="ucv-atendimentos"
      info={<InfoTipContent resumo="Chamados da unidade, do mais recente ao mais antigo. Selecione um protocolo para ver os detalhes."
        nota="A situação considera o fechamento do chamado. A última ação registrada não define se ele está aberto." />}>
      <div className="ucv-history-periods ucv-atendimentos-filtros" role="group" aria-label="Situação dos atendimentos">
        {situacoes.map(item => (
          <button key={item.id} type="button" className="button button--secondary"
            aria-pressed={situacao === item.id}
            onClick={() => { setSituacao(item.id); setPagina(1) }}>
            {item.label} ({formatarNumero(quantidades[item.id])})
          </button>
        ))}
      </div>
      <p className="ucv-atendimentos-descricao">Clique no protocolo para ver os detalhes do chamado.</p>
      {itens.length ? (
        <HistoryTable title="Histórico de chamados de atendimento" columns={['Protocolo', 'Assunto', 'Data de abertura', 'Situação']}
          icon={Headphones} description={vazio} empty={false}>
          {itens.map(item => (
            <tr key={item.protocolo}>
              <th scope="row">
                <button type="button" className="ucv-atendimento-link" aria-haspopup="dialog"
                  aria-label={`Ver detalhes do atendimento ${item.protocolo}`}
                  onClick={() => setAtendimento(item)}>{item.protocolo}</button>
              </th>
              <td>{item.assunto}</td>
              <td>{formatarData(item.data)}</td>
              <td><span className="badge ucv-atendimento" data-status={item.aberto ? 'Aberto' : 'Fechado'}>{item.aberto ? 'Aberto' : 'Fechado'}</span></td>
            </tr>
          ))}
        </HistoryTable>
      ) : <EmptyState compact icon={Headphones} title="Nenhum chamado encontrado" description={vazio} />}
      <div className="table-footer">
        <span role="status">{formatarNumero(filtrados.length)} chamados · página {paginaAtual} de {paginas}</span>
        <span className="pager">
          <button type="button" className="button button--secondary button--small" disabled={paginaAtual <= 1}
            onClick={() => setPagina(paginaAtual - 1)}><ChevronLeft size={14} aria-hidden="true" /> Anterior</button>
          <button type="button" className="button button--secondary button--small" disabled={paginaAtual >= paginas}
            onClick={() => setPagina(paginaAtual + 1)}>Próxima <ChevronRight size={14} aria-hidden="true" /></button>
        </span>
      </div>
      <AtendimentoDialog atendimento={atendimento} onFechar={() => setAtendimento(null)} />
    </Panel>
  )
}
