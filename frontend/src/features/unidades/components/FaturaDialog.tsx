import { useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'
import type { FaturaUC } from '../types'
import { formatarCompetencia, formatarData, formatarMoeda, situacoesFatura } from '../formatters'
import { UnidadeFields } from './UnidadeFields'
import '../../../components/ui/portal.css'

export function FaturaDialog({ fatura, onFechar }: {
  fatura: FaturaUC | null
  onFechar: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const dialogo = ref.current
    if (fatura && !dialogo?.open) dialogo?.showModal()
    if (!fatura && dialogo?.open) dialogo.close()
  }, [fatura])

  return (
    <dialog ref={ref} className="dialog ucv-fatura-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={event => {
        if (event.target === event.currentTarget) event.currentTarget.close()
      }}>
      {fatura && (
        <div className="ucv-fatura-dialog-content">
          <header>
            <h2 id={id}>Fatura de {formatarCompetencia(fatura.competencia)}</h2>
            <button type="button" className="icon-button" aria-label="Fechar detalhes da fatura" onClick={() => ref.current?.close()}>
              <X size={20} aria-hidden="true" />
            </button>
          </header>
          <span className={`badge ucv-fatura--${fatura.status}`}>{situacoesFatura[fatura.status]}</span>
          <UnidadeFields fields={[
            { label: 'Valor total', value: formatarMoeda(fatura.valor_total) },
            { label: 'Valor da energia', value: formatarMoeda(fatura.valor_energia) },
            { label: 'Tributos', value: formatarMoeda(fatura.tributos) },
            { label: 'Bandeira tarifária', value: fatura.bandeira },
            { label: 'Vencimento', value: formatarData(fatura.vencimento) },
            { label: 'Pagamento', value: fatura.status === 'paga' ? formatarData(fatura.data_pagamento) : 'Em aberto' },
          ]} />
        </div>
      )}
    </dialog>
  )
}
