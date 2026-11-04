import { useEffect, useId, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { InfoTipContent } from '../../../components/ui/InfoTip'
import { EmptyState } from '../../../components/ui/EmptyState'
import { SelectField } from '../../../components/ui/Controls'
import { ErrorState, LoadingState } from '../../../components/ui/Feedback'
import { consultarFaturas } from '../api'
import type { AbaFaturas, FaturaUC, PaginaFaturasUC, SituacaoFaturas, Visao360 } from '../types'
import { faixasAtraso, formatarCompetencia, formatarData, formatarMoeda, formatarNumero, situacoesFatura } from '../formatters'
import { BandeiraTarifaria } from './BandeiraTarifaria'
import { FaturaDialog } from './FaturaDialog'

const abas: { id: AbaFaturas; label: string; descricao: string; vazio: string }[] = [
  {
    id: 'recentes', label: 'Recentes',
    descricao: 'Últimas 12 competências disponíveis, sem pendências com mais de 90 dias.',
    vazio: 'Não há faturas pagas ou pendências recentes nas últimas 12 competências desta UC.',
  },
  {
    id: 'historico', label: 'Histórico completo',
    descricao: 'Todas as competências. Filtre por ano e situação para consultar o histórico.',
    vazio: 'Não há faturas para o ano e a situação selecionados.',
  },
]

type FiltroFaturas = { aba: AbaFaturas; ano: string; situacao: SituacaoFaturas; pagina: number }
type ConsultaFaturas = { chave: string; dados: PaginaFaturasUC | null; erro: Error | null }

export function FaturasSection({ dados }: { dados: Visao360 }) {
  const [filtro, setFiltro] = useState<FiltroFaturas>({ aba: 'recentes', ano: '', situacao: 'todas', pagina: 1 })
  const [consulta, setConsulta] = useState<ConsultaFaturas | null>(null)
  const [tentativa, setTentativa] = useState(0)
  const [fatura, setFatura] = useState<FaturaUC | null>(null)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const id = useId()
  const ucId = dados.cadastro.uc_id
  const chave = JSON.stringify([ucId, filtro, tentativa])
  const resultado = consulta?.dados ?? null
  const carregando = consulta?.chave !== chave
  const erro = carregando ? null : consulta?.erro

  useEffect(() => {
    const controller = new AbortController()
    consultarFaturas(ucId, filtro.aba, filtro.ano, filtro.situacao, filtro.pagina, controller.signal)
      .then(resposta => {
        if (!controller.signal.aborted) setConsulta({ chave, dados: resposta, erro: null })
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setConsulta(anterior => ({
            chave, dados: anterior?.dados ?? null,
            erro: error instanceof Error ? error : new Error('Não foi possível consultar as faturas.'),
          }))
        }
      })
    return () => controller.abort()
  }, [ucId, filtro, chave])

  const ativa = abas.find(aba => aba.id === filtro.aba)!
  const resumo = resultado?.resumo ?? dados.resumo_faturas
  const paginas = Math.max(1, Math.ceil((resultado?.total ?? 0) / (resultado?.tamanho ?? 6)))
  function trocarAba(aba: AbaFaturas) {
    setFiltro({ aba, ano: '', situacao: 'todas', pagina: 1 })
  }

  return (
    <Panel title="Faturas e pagamentos" description="Consulte faturas recentes e o histórico completo de pagamentos e pendências." className="panel--filters ucv-faturas"
      info={<InfoTipContent resumo="Consulte o valor total, o pagamento e a situação de cada fatura." itens={[
        { rotulo: 'Recentes', texto: 'Últimas 12 competências, sem pendências com mais de 90 dias de atraso.' },
        { rotulo: 'Histórico completo', texto: 'Inclui as pendências antigas, com filtros por ano e situação.' },
      ]} nota="As contagens de pendências consideram todo o histórico da unidade, independentemente dos filtros." />}>
      <div className="ucv-faturas-resumo" aria-label="Pendências em todas as competências da UC">
        <div>
          <span>Pendências recentes</span>
          <strong>{formatarNumero(resumo.pendencias_recentes)}</strong>
          <small>Até 90 dias de atraso ou ainda não vencidas</small>
        </div>
        <div>
          <span>Pendências antigas</span>
          <strong>{formatarNumero(resumo.pendencias_antigas)}</strong>
          <small>Mais de 90 dias de atraso</small>
        </div>
      </div>
      <div className="ucv-tabs ucv-faturas-tabs" role="tablist" aria-label="Consulta de faturas">
        {abas.map((aba, index) => (
          <button
            key={aba.id} type="button" role="tab" id={`${id}-${aba.id}`}
            aria-selected={filtro.aba === aba.id} aria-controls={`${id}-panel`}
            tabIndex={filtro.aba === aba.id ? 0 : -1}
            ref={el => { tabRefs.current[index] = el }}
            onClick={() => trocarAba(aba.id)} onKeyDown={event => {
            let proximo: number
            if (event.key === 'ArrowRight') proximo = (index + 1) % abas.length
            else if (event.key === 'ArrowLeft') proximo = (index + abas.length - 1) % abas.length
            else if (event.key === 'Home') proximo = 0
            else if (event.key === 'End') proximo = abas.length - 1
            else return
            event.preventDefault()
            trocarAba(abas[proximo].id)
            tabRefs.current[proximo]?.focus()
          }}>{aba.label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${ativa.id}`} tabIndex={0}>
        <p className="ucv-faturas-descricao">{ativa.descricao} Clique numa fatura para ver os detalhes.</p>
        {filtro.aba === 'historico' && (
          <div className="filters" aria-label="Filtros do histórico de faturas">
            <SelectField label="Ano" value={filtro.ano} placeholder="Todos os anos"
              options={(resultado?.anos_disponiveis ?? []).map(ano => ({ value: String(ano), label: String(ano) }))}
              onChange={ano => setFiltro({ ...filtro, ano, pagina: 1 })} />
            <SelectField label="Situação" value={filtro.situacao === 'todas' ? '' : filtro.situacao}
              options={[{ value: 'paga', label: 'Paga' }, { value: 'em_aberto', label: 'Em aberto' }]}
              placeholder="Todas"
              onChange={situacao => setFiltro({ ...filtro, situacao: (situacao || 'todas') as SituacaoFaturas, pagina: 1 })} />
          </div>
        )}
        <div className="ucv-faturas-resultados" aria-busy={carregando}>
          {erro ? <ErrorState error={erro} onRetry={() => setTentativa(n => n + 1)} /> : !resultado ? <LoadingState label="Consultando faturas…" /> : resultado.itens.length ? (
            <div className="ucv-faturas-lista-scroll">
              <div className="ucv-fatura-item ucv-fatura-item--cabecalho" aria-hidden="true">
                <span>Competência</span><span>Bandeira</span><span>Consumo</span><span>Total</span><span>Situação</span><span />
              </div>
              <ul className="ucv-faturas-lista" aria-label="Faturas e pagamentos da UC">
                {resultado.itens.map(item => (
                  <li key={item.id_fatura ?? item.competencia}>
                    <button type="button" className="ucv-fatura-item" disabled={carregando} aria-haspopup="dialog"
                      aria-label={`Ver detalhes da fatura de ${formatarCompetencia(item.competencia)}`} onClick={() => setFatura(item)}>
                      <span className="ucv-fatura-item-competencia">
                        <strong>{formatarCompetencia(item.competencia)}</strong>
                        <small>Vence em {formatarData(item.vencimento)}</small>
                      </span>
                      <BandeiraTarifaria bandeira={item.bandeira} />
                      <span className="ucv-fatura-item-consumo">{formatarNumero(item.consumo_kwh)} kWh</span>
                      <strong className="ucv-fatura-item-valor">{formatarMoeda(item.valor_total)}</strong>
                      <span className="ucv-fatura-item-situacao">
                        <span className={`badge ucv-fatura--${item.status}`}>{situacoesFatura[item.status]}</span>
                        <small>{item.status === 'paga' ? `Paga em ${formatarData(item.data_pagamento)}` : faixasAtraso[item.faixa_atraso]}</small>
                      </span>
                      <ChevronRight className="ucv-fatura-item-seta" size={16} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : <EmptyState compact icon={FileText} title="Nenhuma fatura encontrada" description={resultado.total > 0 ? 'Não há faturas nesta página. Volte para a página anterior.' : ativa.vazio} />}
        </div>
        <div className="table-footer">
          <span role="status">{carregando ? 'Atualizando faturas…' : resultado && !erro ? `${formatarNumero(resultado.total)} faturas · página ${resultado.pagina} de ${paginas}` : ''}</span>
          <span className="pager">
            <button type="button" className="button button--secondary button--small"
              disabled={carregando || !!erro || filtro.pagina <= 1}
              onClick={() => setFiltro({ ...filtro, pagina: filtro.pagina - 1 })}>
              <ChevronLeft size={14} aria-hidden="true" /> Anterior
            </button>
            <button type="button" className="button button--secondary button--small"
              disabled={carregando || !!erro || filtro.pagina >= paginas}
              onClick={() => setFiltro({ ...filtro, pagina: filtro.pagina + 1 })}>
              Próxima <ChevronRight size={14} aria-hidden="true" />
            </button>
          </span>
        </div>
      </div>
      <FaturaDialog fatura={fatura} onFechar={() => setFatura(null)} />
    </Panel>
  )
}
