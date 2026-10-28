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

export type PeriodoSelecionado = { inicio: string; fim: string }

type SeletorPeriodoProps = {
  label: string
  valor: PeriodoSelecionado | null
  minimo: string
  maximo: string
  onChange: (periodo: PeriodoSelecionado) => void
}

function formatarMes(competencia: string) {
  const [ano, mes] = competencia.split('-')
  return `${meses[Number(mes) - 1].slice(0, 3)}/${ano}`
}

export function SeletorPeriodo({
  label,
  valor,
  minimo,
  maximo,
  onChange,
}: SeletorPeriodoProps) {
  const [aberto, setAberto] = useState(false)
  const [ano, setAno] = useState(Number((valor?.inicio ?? maximo).slice(0, 4)))
  const [inicioPendente, setInicioPendente] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const botaoRef = useRef<HTMLButtonElement>(null)
  const id = useId()
  const inicio = inicioPendente ?? valor?.inicio
  const fim = inicioPendente ?? valor?.fim

  useEffect(() => {
    if (!aberto) return
    const foco =
      containerRef.current?.querySelector<HTMLButtonElement>(
        '.dashboard-period-month[aria-pressed="true"]',
      ) ??
      containerRef.current?.querySelector<HTMLButtonElement>(
        '.dashboard-period-month:not(:disabled)',
      )
    foco?.focus({ preventScroll: true })

    function fecharFora(event: Event) {
      if (
        event.target instanceof Node &&
        !containerRef.current?.contains(event.target)
      ) {
        setAberto(false)
        setInicioPendente(null)
      }
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
    setInicioPendente(null)
    botaoRef.current?.focus({ preventScroll: true })
  }

  function selecionar(competencia: string) {
    if (inicioPendente === null) {
      setInicioPendente(competencia)
      return
    }
    onChange({
      inicio: competencia < inicioPendente ? competencia : inicioPendente,
      fim: competencia > inicioPendente ? competencia : inicioPendente,
    })
    fechar()
  }

  return (
    <div
      className="dashboard-filter dashboard-period-picker"
      ref={containerRef}
      onKeyDown={(event) => {
        if (aberto && event.key === 'Escape') {
          event.preventDefault()
          event.stopPropagation()
          fechar()
        }
      }}
    >
      <label htmlFor={id} id={`${id}-label`}>
        {label}
      </label>
      <button
        id={id}
        ref={botaoRef}
        type="button"
        className="dashboard-filter-trigger"
        aria-labelledby={`${id}-label ${id}-value`}
        aria-haspopup="dialog"
        aria-expanded={aberto}
        aria-controls={aberto ? `${id}-dialog` : undefined}
        onClick={() => {
          setAno(Number((valor?.inicio ?? maximo).slice(0, 4)))
          setInicioPendente(null)
          setAberto(!aberto)
        }}
      >
        <CalendarDays size={15} aria-hidden="true" />
        <span id={`${id}-value`}>
          {valor === null
            ? 'Selecionar período'
            : valor.inicio === valor.fim
              ? formatarMes(valor.inicio)
              : `${formatarMes(valor.inicio)} a ${formatarMes(valor.fim)}`}
        </span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {aberto && (
        <div
          id={`${id}-dialog`}
          role="dialog"
          aria-label={`Selecionar ${label.toLowerCase()}`}
          aria-describedby={`${id}-ajuda`}
          className="dashboard-period-popover"
        >
          <div className="dashboard-period-year">
            <button
              type="button"
              aria-label="Ano anterior"
              disabled={ano <= Number(minimo.slice(0, 4))}
              onClick={() => setAno(ano - 1)}
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <strong aria-live="polite">{ano}</strong>
            <button
              type="button"
              aria-label="Próximo ano"
              disabled={ano >= Number(maximo.slice(0, 4))}
              onClick={() => setAno(ano + 1)}
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
          <div
            className="dashboard-period-grid"
            role="group"
            aria-label={`Meses de ${ano}`}
          >
            {meses.map((mes, indice) => {
              const competencia = `${ano}-${String(indice + 1).padStart(2, '0')}`
              return (
                <button
                  key={mes}
                  type="button"
                  className="dashboard-period-month"
                  aria-label={`${mes} de ${ano}`}
                  aria-pressed={
                    inicio !== undefined &&
                    fim !== undefined &&
                    competencia >= inicio &&
                    competencia <= fim
                  }
                  data-extremidade={
                    competencia === inicio || competencia === fim
                  }
                  disabled={competencia < minimo || competencia > maximo}
                  onClick={() => selecionar(competencia)}
                >
                  {mes.slice(0, 3)}
                </button>
              )
            })}
          </div>
          <p
            id={`${id}-ajuda`}
            className="dashboard-period-help"
            aria-live="polite"
          >
            {inicioPendente
              ? `${formatarMes(inicioPendente)} selecionado. Clique no mês final ou no mesmo mês para selecionar somente ele.`
              : 'Clique no mês inicial e depois no final. Para um único mês, clique duas vezes nele.'}
          </p>
        </div>
      )}
    </div>
  )
}
