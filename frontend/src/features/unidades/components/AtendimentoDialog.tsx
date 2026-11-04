import { useEffect, useId, useRef } from 'react'
import { Headphones, X } from 'lucide-react'
import type { AtendimentoUC } from '../types'
import { formatarDataHora, formatarNotaSatisfacao, formatarNumero, formatarRotulo, formatarTempoResolucao } from '../formatters'
import { UnidadeFields } from './UnidadeFields'
import '../../../components/ui/portal.css'

export function AtendimentoDialog({ atendimento, onFechar }: {
  atendimento: AtendimentoUC | null
  onFechar: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const dialogo = ref.current
    if (atendimento && !dialogo?.open) dialogo?.showModal()
    if (!atendimento && dialogo?.open) dialogo.close()
  }, [atendimento])

  const situacao = atendimento?.aberto ? 'Aberto' : 'Fechado'

  return (
    <dialog ref={ref} className="dialog ucv-atendimento-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={event => {
        if (event.target === event.currentTarget) event.currentTarget.close()
      }}>
      {atendimento && (
        <div className="ucv-atendimento-dialog-content">
          <header>
            <div className="ucv-dialog-titulo">
              <span className="ucv-dialog-icone"><Headphones size={20} aria-hidden="true" /></span>
              <div>
                <h2 id={id}>Atendimento {atendimento.protocolo}</h2>
                <p>Aberto em {formatarDataHora(atendimento.data)}</p>
              </div>
            </div>
            <button type="button" className="icon-button" aria-label="Fechar detalhes do atendimento" onClick={() => ref.current?.close()}>
              <X size={20} aria-hidden="true" />
            </button>
          </header>

          <div className="ucv-dialog-destaque ucv-dialog-destaque--texto">
            <div>
              <span>Assunto</span>
              <strong>{formatarRotulo(atendimento.assunto)}</strong>
              <small>{formatarRotulo(atendimento.subassunto)}</small>
            </div>
            <div className="ucv-dialog-selos">
              <span className="badge ucv-atendimento" data-status={situacao}>{situacao}</span>
              <span className="ucv-atendimento-canal">{formatarRotulo(atendimento.canal)}</span>
            </div>
          </div>

          {/* Da abertura ao fechamento, com o tempo de resolução no meio. */}
          <div className="ucv-atendimento-linha" data-aberto={atendimento.aberto}>
            <div className="ucv-atendimento-marco">
              <i aria-hidden="true" />
              <span>Abertura</span>
              <strong>{formatarDataHora(atendimento.data)}</strong>
            </div>
            <div className="ucv-atendimento-trilho" aria-hidden="true">
              <span>{atendimento.aberto ? 'Em andamento' : `Resolvido em ${formatarTempoResolucao(atendimento.tempo_resolucao_horas)}`}</span>
            </div>
            <div className="ucv-atendimento-marco ucv-atendimento-marco--fim">
              <i aria-hidden="true" />
              <span>Fechamento</span>
              <strong>{atendimento.data_fechamento ? formatarDataHora(atendimento.data_fechamento) : atendimento.aberto ? 'Ainda não fechado' : 'Não disponível'}</strong>
            </div>
          </div>
          {!atendimento.aberto && <p className="sr-only">Tempo de resolução: {formatarTempoResolucao(atendimento.tempo_resolucao_horas)}.</p>}

          <UnidadeFields fields={[
            { label: 'Canal de atendimento', value: formatarRotulo(atendimento.canal) },
            { label: 'Última ação', value: formatarRotulo(atendimento.ultima_acao) },
            { label: 'Tratativas', value: formatarNumero(atendimento.qtd_tratativas) },
            { label: 'Nota de satisfação', value: formatarNotaSatisfacao(atendimento.nota_satisfacao) },
          ]} />
        </div>
      )}
    </dialog>
  )
}
