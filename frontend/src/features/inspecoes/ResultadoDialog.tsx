import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../api'
import type { Ordem, TipoIrregularidade } from '../../api'
import { mensagemDeErro } from '../../utils/format'
import '../../components/ui/portal.css'
import { TIPOS } from './tipos'

type Props = {
  ordem: Ordem | null
  onFechar: () => void
  onRegistrado: (ordem: Ordem) => void
}

export function ResultadoDialog({ ordem, onFechar, onRegistrado }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const [tipo, setTipo] = useState<TipoIrregularidade | ''>('')
  const [energia, setEnergia] = useState('')
  const [observacoes, setObservacoes] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo) return
    if (ordem && !dialogo.open) {
      setTipo('')
      setEnergia('')
      setObservacoes('')
      setErro(null)
      dialogo.showModal()
    }
    if (!ordem && dialogo.open) dialogo.close()
  }, [ordem])

  const semIrregularidade = tipo === 'nenhuma'

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    if (!ordem || !tipo) return
    const kwh = semIrregularidade || energia.trim() === '' ? 0 : Number(energia.replace(',', '.'))
    if (!Number.isFinite(kwh) || kwh < 0) {
      setErro('Informe a energia recuperada como um número maior ou igual a zero.')
      return
    }
    setEnviando(true)
    setErro(null)
    try {
      const atualizada = await api.perdas.registrarResultado(ordem.id, {
        tipo,
        energia_recuperada_kwh: kwh,
        observacoes: observacoes.trim() || null,
      })
      onRegistrado(atualizada)
    } catch (e) {
      setErro(mensagemDeErro(e))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <dialog ref={ref} className="dialog" aria-labelledby="titulo-resultado" onClose={onFechar}>
      <form onSubmit={enviar}>
        <h2 id="titulo-resultado">Registrar resultado · ordem #{ordem?.id}</h2>
        <p className="muted">Unidade consumidora {ordem?.uc_id}. O resultado conclui a ordem.</p>
        <label className="field">
          <span>O que a equipe encontrou *</span>
          <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoIrregularidade | '')} required>
            <option value="">Selecione…</option>
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Energia recuperada (kWh)</span>
          <input
            inputMode="decimal"
            value={semIrregularidade ? '0' : energia}
            disabled={semIrregularidade}
            onChange={(e) => setEnergia(e.target.value)}
            placeholder="0"
          />
          {semIrregularidade && <span className="field-hint">Sem irregularidade, não há energia a recuperar.</span>}
        </label>
        <label className="field">
          <span>Observações</span>
          <textarea rows={3} maxLength={500} value={observacoes} onChange={(e) => setObservacoes(e.target.value)} />
        </label>
        {erro && (
          <p className="notice notice--error" role="alert">
            {erro}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button button--secondary" onClick={onFechar} disabled={enviando}>
            Cancelar
          </button>
          <button type="submit" className="button button--primary" disabled={!tipo || enviando}>
            {enviando ? 'Salvando…' : 'Registrar resultado'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
