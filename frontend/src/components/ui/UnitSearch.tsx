import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { CircleAlert, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { identificadorUCValido, normalizarIdentificadorUC } from '../../utils/uc'
import './unit-search.css'

type UnitSearchProps = {
  compact?: boolean
}

export function UnitSearch({ compact = false }: UnitSearchProps) {
  const [value, setValue] = useState('')
  const [erro, setErro] = useState<'vazio' | 'formato' | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const feedbackRef = useRef<HTMLDivElement>(null)
  const [posicao, setPosicao] = useState<{ left: number; top: number; seta: number; acima: boolean } | null>(null)
  const feedbackId = useId()
  const navigate = useNavigate()

  useLayoutEffect(() => {
    if (!erro) return
    function posicionar() {
      const campo = inputRef.current?.getBoundingClientRect()
      const controle = inputRef.current?.closest('form')?.getBoundingClientRect()
      const aviso = feedbackRef.current?.getBoundingClientRect()
      if (!campo || !controle || !aviso) return
      const margem = 12
      const left = Math.max(margem, Math.min(compact ? controle.right - aviso.width : controle.left, window.innerWidth - aviso.width - margem))
      const acima = controle.bottom + aviso.height + 10 > window.innerHeight - margem && controle.top > aviso.height + 10
      const top = acima ? controle.top - aviso.height - 10 : controle.bottom + 10
      setPosicao({ left, top, acima, seta: Math.max(16, Math.min(campo.left + 18 - left, aviso.width - 16)) })
    }
    posicionar()
    window.addEventListener('resize', posicionar)
    document.addEventListener('scroll', posicionar, true)
    return () => {
      window.removeEventListener('resize', posicionar)
      document.removeEventListener('scroll', posicionar, true)
    }
  }, [erro, compact])

  useEffect(() => {
    if (!erro) return
    function fora(event: PointerEvent) {
      if (event.target instanceof Node && !feedbackRef.current?.contains(event.target)
        && !inputRef.current?.closest('form')?.contains(event.target)) setErro(null)
    }
    function tecla(event: KeyboardEvent) { if (event.key === 'Escape') setErro(null) }
    document.addEventListener('pointerdown', fora)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('pointerdown', fora)
      document.removeEventListener('keydown', tecla)
    }
  }, [erro])

  return (
    <div className={`unit-search-container${compact ? ' unit-search-container--compact' : ''}`}>
      <form
        className={`unit-search${compact ? ' unit-search--compact' : ''}`}
        noValidate
        data-invalid={erro ? 'true' : undefined}
        role="search"
        aria-label={
          compact
            ? 'Busca global de unidade consumidora'
            : 'Buscar unidade consumidora'
        }
        onSubmit={(event) => {
          event.preventDefault()
          if (!identificadorUCValido(value)) {
            setErro(value.trim() ? 'formato' : 'vazio')
            inputRef.current?.focus()
            return
          }
          setErro(null)
          navigate(`/uc/${encodeURIComponent(normalizarIdentificadorUC(value))}`)
          setValue('')
        }}
      >
        <Search size={18} aria-hidden="true" />
        <input
          ref={inputRef}
          id={compact ? 'global-uc-search' : 'page-uc-search'}
          aria-label="Identificador da unidade consumidora"
          aria-invalid={erro ? true : undefined}
          aria-describedby={erro ? feedbackId : undefined}
          placeholder={compact ? 'Buscar UC...' : 'Ex.: UC100000'}
          value={value}
          onChange={(event) => {
            setErro(null)
            setValue(event.target.value.trim().toUpperCase())
          }}
          pattern="(UC)?[0-9]{6}"
          autoComplete="off"
          maxLength={100}
          required
        />
        {compact ? (
          <kbd aria-hidden="true">Ctrl K</kbd>
        ) : (
          <button className="button button--primary" type="submit">
            Buscar UC
          </button>
        )}
      </form>
      {erro && createPortal(<div ref={feedbackRef} id={feedbackId} className="unit-search-feedback" role="alert"
        data-acima={posicao?.acima || undefined}
        style={{ left: posicao?.left ?? 0, top: posicao?.top ?? 0, visibility: posicao ? 'visible' : 'hidden', '--unit-search-seta': `${posicao?.seta ?? 24}px` } as CSSProperties}>
        <CircleAlert size={18} aria-hidden="true" />
        <div>
          <strong>{erro === 'vazio' ? 'Qual UC você quer consultar?' : 'Confira o identificador da UC'}</strong>
          <span>Informe os seis dígitos da conta, com ou sem o prefixo UC.</span>
          <span className="unit-search-feedback-exemplos">Exemplo: <code>000001</code> ou <code>UC000001</code></span>
        </div>
      </div>, document.body)}
    </div>
  )
}
