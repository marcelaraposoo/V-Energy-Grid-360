import { useEffect, useId, useRef } from 'react'
import { FileText, X } from 'lucide-react'
import type { FaturaUC } from '../types'
import {
  faixasAtraso, formatarCompetencia, formatarData, formatarMoeda, formatarNumero, formatarParticipacao, formatarPrecoKwh,
  situacoesFatura,
} from '../formatters'
import { BandeiraTarifaria } from './BandeiraTarifaria'
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

  // Composição do total: energia (com bandeira) + tributos, quando os dois vieram.
  const energia = fatura?.valor_energia ?? null
  const tributos = fatura?.tributos ?? null
  const soma = energia !== null && tributos !== null ? energia + tributos : 0
  const parteEnergia = soma > 0 && energia !== null ? energia / soma : null

  return (
    <dialog ref={ref} className="dialog ucv-fatura-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={event => {
        if (event.target === event.currentTarget) event.currentTarget.close()
      }}>
      {fatura && (
        <div className="ucv-fatura-dialog-content">
          <header>
            <div className="ucv-dialog-titulo">
              <span className="ucv-dialog-icone"><FileText size={20} aria-hidden="true" /></span>
              <div>
                <h2 id={id}>Fatura de {formatarCompetencia(fatura.competencia)}</h2>
                <p>{fatura.status === 'paga' ? `Paga em ${formatarData(fatura.data_pagamento)}` : faixasAtraso[fatura.faixa_atraso]}</p>
              </div>
            </div>
            <button type="button" className="icon-button" aria-label="Fechar detalhes da fatura" onClick={() => ref.current?.close()}>
              <X size={20} aria-hidden="true" />
            </button>
          </header>

          <div className="ucv-dialog-destaque">
            <div>
              <span>Valor total</span>
              <strong>{formatarMoeda(fatura.valor_total)}</strong>
            </div>
            <div className="ucv-dialog-selos">
              <span className={`badge ucv-fatura--${fatura.status}`}>{situacoesFatura[fatura.status]}</span>
              <BandeiraTarifaria bandeira={fatura.bandeira} />
            </div>
          </div>

          {parteEnergia !== null && (
            <div className="ucv-fatura-dialog-composicao">
              <div className="ucv-fatura-dialog-barra" role="img"
                aria-label={`Energia: ${formatarParticipacao(parteEnergia)} do total; tributos: ${formatarParticipacao(1 - parteEnergia)}.`}>
                <span className="ucv-fatura-dialog-barra-energia" style={{ width: `${parteEnergia * 100}%` }} />
                <span className="ucv-fatura-dialog-barra-tributos" style={{ width: `${(1 - parteEnergia) * 100}%` }} />
              </div>
              <dl className="ucv-fatura-dialog-legenda">
                <div>
                  <dt><i className="ucv-fatura-dialog-ponto--energia" aria-hidden="true" />Energia</dt>
                  <dd>{formatarMoeda(energia)} <small>{formatarParticipacao(parteEnergia)}</small></dd>
                </div>
                <div>
                  <dt><i className="ucv-fatura-dialog-ponto--tributos" aria-hidden="true" />Tributos</dt>
                  <dd>{formatarMoeda(tributos)} <small>{formatarParticipacao(1 - parteEnergia)}</small></dd>
                </div>
              </dl>
            </div>
          )}

          <UnidadeFields fields={[
            { label: 'Consumo faturado (kWh)', value: formatarNumero(fatura.consumo_kwh) },
            { label: 'Preço médio por kWh', value: formatarPrecoKwh(fatura.preco_medio_kwh) },
            { label: 'Vencimento', value: formatarData(fatura.vencimento) },
            { label: 'Pagamento', value: fatura.status === 'paga' ? formatarData(fatura.data_pagamento) : 'Em aberto' },
          ]} />
          <p className="ucv-dialog-nota">
            O valor da energia e o preço médio por kWh incluem o adicional de bandeira e não incluem tributos.
          </p>
        </div>
      )}
    </dialog>
  )
}
