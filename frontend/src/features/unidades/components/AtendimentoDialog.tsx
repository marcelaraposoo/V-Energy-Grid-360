import { useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'
import type { AtendimentoUC } from '../types'
import { formatarDataHora, formatarNotaSatisfacao } from '../formatters'
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

  return (
    <dialog ref={ref} className="dialog ucv-atendimento-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={event => {
        if (event.target === event.currentTarget) event.currentTarget.close()
      }}>
      {atendimento && (
        <div className="ucv-atendimento-dialog-content">
          <header>
            <h2 id={id}>Atendimento {atendimento.protocolo}</h2>
            <button type="button" className="icon-button" aria-label="Fechar detalhes do atendimento" onClick={() => ref.current?.close()}>
              <X size={20} aria-hidden="true" />
            </button>
          </header>
          <span className="badge ucv-atendimento" data-status={atendimento.aberto ? 'Aberto' : 'Fechado'}>
            {atendimento.aberto ? 'Aberto' : 'Fechado'}
          </span>
          <UnidadeFields fields={[
            { label: 'Assunto', value: atendimento.assunto },
            { label: 'Subassunto', value: atendimento.subassunto },
            { label: 'Canal de atendimento', value: atendimento.canal },
            { label: 'Última ação', value: atendimento.ultima_acao },
            { label: 'Data e hora de abertura', value: formatarDataHora(atendimento.data) },
            { label: 'Data e hora de fechamento', value: atendimento.data_fechamento ? formatarDataHora(atendimento.data_fechamento) : atendimento.aberto ? 'Ainda não fechado' : 'Não disponível' },
            ...(atendimento.nota_satisfacao === null ? [] : [
              { label: 'Nota de satisfação', value: formatarNotaSatisfacao(atendimento.nota_satisfacao) },
            ]),
          ]} />
        </div>
      )}
    </dialog>
  )
}
