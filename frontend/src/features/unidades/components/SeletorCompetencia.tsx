import { useEffect, useId, useRef, useState } from 'react'
import {
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

const meses = [
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
]

type SeletorCompetenciaProps = {
  label: string
  valor: string | null
  competencias: string[]
  vazio: string
  onChange: (competencia: string) => void
}

export function SeletorCompetencia({
  label,
  valor,
  competencias,
  vazio,
  onChange,
}: SeletorCompetenciaProps) {
  const [aberto, setAberto] = useState(false)
  const [ano, setAno] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const botaoRef = useRef<HTMLButtonElement>(null)
  const id = useId()
  const anos = [...new Set(competencias.map((c) => Number(c.slice(0, 4))))]
  const indiceAno = anos.indexOf(ano)
  const [anoSelecionado, mesSelecionado] = (valor ?? '').split('-')

  useEffect(() => {
    if (!aberto) return
    const selecionado = containerRef.current?.querySelector<HTMLButtonElement>(
      '.ucv-month-picker-month[aria-pressed="true"]',
    )
    const primeiro = containerRef.current?.querySelector<HTMLButtonElement>(
      '.ucv-month-picker-month:not(:disabled)',
    )
    const foco = selecionado ?? primeiro
    foco?.focus()
    function fecharFora(event: Event) {
      if (
        event.target instanceof Node &&
        !containerRef.current?.contains(event.target)
      )
        setAberto(false)
    }
    document.addEventListener('pointerdown', fecharFora)
    document.addEventListener('focusin', fecharFora)
    return () => {
      document.removeEventListener('pointerdown', fecharFora)
      document.removeEventListener('focusin', fecharFora)
    }
  }, [aberto])

  function fechar() {
    setAberto(false)
    botaoRef.current?.focus()
  }

  return (
    <div
      className="ucv-month-picker"
      ref={containerRef}
      onKeyDown={(event) => {
        if (aberto && event.key === 'Escape') {
          event.preventDefault()
          event.stopPropagation()
          fechar()
        }
      }}
    >
      <label id={`${id}-label`} className="ucv-comparison-label" htmlFor={id}>
        {label}
      </label>
      <button
        ref={botaoRef}
        id={id}
        type="button"
        className="ucv-month-picker-trigger"
        disabled={!competencias.length}
        aria-labelledby={`${id}-label ${id}-value`}
        aria-haspopup="dialog"
        aria-expanded={aberto}
        aria-controls={aberto ? `${id}-dialog` : undefined}
        onClick={() => {
          const competencia = valor ?? competencias.at(-1)
          if (!competencia) return
          setAno(Number(competencia.slice(0, 4)))
          setAberto(!aberto)
        }}
      >
        <CalendarDays size={16} aria-hidden="true" />
        <span id={`${id}-value`}>
          {valor
            ? `${meses[Number(mesSelecionado) - 1]}/${anoSelecionado}`
            : vazio}
        </span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {aberto && (
        <div
          id={`${id}-dialog`}
          role="dialog"
          aria-label={`Selecionar ${label.toLowerCase()}`}
          className="ucv-month-picker-popover"
        >
          <div className="ucv-month-picker-year">
            <button
              type="button"
              aria-label="Ano anterior com histórico"
              disabled={indiceAno <= 0}
              onClick={() => setAno(anos[indiceAno - 1])}
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <strong aria-live="polite">{ano}</strong>
            <button
              type="button"
              aria-label="Próximo ano com histórico"
              disabled={indiceAno >= anos.length - 1}
              onClick={() => setAno(anos[indiceAno + 1])}
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
          <div
            className="ucv-month-picker-grid"
            role="group"
            aria-label={`Meses de ${ano}`}
          >
            {meses.map((mes, indice) => {
              const competencia = `${ano}-${String(indice + 1).padStart(2, '0')}`
              return (
                <button
                  key={mes}
                  type="button"
                  className="ucv-month-picker-month"
                  aria-label={`${mes} de ${ano}`}
                  aria-pressed={valor === competencia}
                  disabled={!competencias.includes(competencia)}
                  onClick={() => {
                    fechar()
                    if (competencia !== valor) onChange(competencia)
                  }}
                >
                  {mes.slice(0, 3)}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
