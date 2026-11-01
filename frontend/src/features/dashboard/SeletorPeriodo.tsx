import { useEffect, useId, useRef, useState } from 'react'
import {
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react'
import type { Periodo } from '../../api/types'
import { deslocarMes } from '../../utils/periodosDashboard'
import '../../components/ui/controls.css'

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

export type PeriodoSelecionado = Periodo

type SeletorPeriodoProps = {
  label: string
  valor: PeriodoSelecionado | null
  minimo: string
  maximo: string
  desabilitado?: boolean
  sugestao?: Periodo | null
  mesesFixos?: number
  validar?: (periodo: Periodo) => string | null
  onLimpar?: () => void
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
  desabilitado,
  sugestao,
  mesesFixos,
  validar,
  onLimpar,
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
        '.dashboard-period-month[aria-pressed="true"]:not(:disabled)',
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

  function alternar() {
    setAno(Number((valor?.inicio ?? sugestao?.inicio ?? maximo).slice(0, 4)))
    setInicioPendente(null)
    setAberto(!aberto)
  }

  function selecionar(competencia: string) {
    if (mesesFixos !== undefined) {
      const selecionado = { inicio: competencia, fim: deslocarMes(competencia, mesesFixos - 1) }
      if (mesesFixos < 1 || selecionado.inicio < minimo || selecionado.fim > maximo || validar?.(selecionado)) return
      onChange(selecionado)
      fechar()
      return
    }
    if (inicioPendente === null) {
      setInicioPendente(competencia)
      return
    }
    const selecionado = {
      inicio: competencia < inicioPendente ? competencia : inicioPendente,
      fim: competencia > inicioPendente ? competencia : inicioPendente,
    }
    if (validar?.(selecionado)) return
    onChange(selecionado)
    fechar()
  }

  return (
    <div
      className="filter-field dashboard-period-picker"
      ref={containerRef}
      onKeyDown={(event) => {
        if (aberto && event.key === 'Escape') {
          event.preventDefault()
          event.stopPropagation()
          fechar()
        }
      }}
    >
      <label htmlFor={id} id={`${id}-label`}>{label}</label>
      <div className="filter-trigger dashboard-period-control" data-disabled={desabilitado}>
        <CalendarDays size={15} aria-hidden="true" />
        <div className="dashboard-period-selection">
          <button
            id={id}
            ref={botaoRef}
            type="button"
            disabled={desabilitado}
            className="dashboard-period-value"
            aria-labelledby={`${id}-label ${id}-value`}
            aria-haspopup="dialog"
            aria-expanded={aberto}
            aria-controls={aberto ? `${id}-dialog` : undefined}
            onClick={alternar}
          >
            <span id={`${id}-value`}>
              {valor === null
                ? 'Selecionar período'
                : valor.inicio === valor.fim
                  ? formatarMes(valor.inicio)
                  : `${formatarMes(valor.inicio)} a ${formatarMes(valor.fim)}`}
            </span>
          </button>
        </div>
        <button type="button" className="dashboard-period-expand" disabled={desabilitado} tabIndex={-1}
          aria-label={`Abrir ${label.toLowerCase()}`} onClick={alternar}>
          <ChevronDown size={14} aria-hidden="true" />
        </button>
        {onLimpar && valor && (
          <button type="button" className="dashboard-period-clear" aria-label="Remover período de referência"
            disabled={desabilitado} onClick={() => {
              setAberto(false)
              setInicioPendente(null)
              onLimpar()
              botaoRef.current?.focus({ preventScroll: true })
            }}>
            <X size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      {aberto && !desabilitado && (
        <div
          id={`${id}-dialog`}
          role="dialog"
          tabIndex={-1}
          aria-label={`Selecionar ${label.toLowerCase()}`}
          aria-describedby={mesesFixos === undefined ? `${id}-ajuda` : undefined}
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
              const candidato = mesesFixos !== undefined
                ? { inicio: competencia, fim: deslocarMes(competencia, mesesFixos - 1) }
                : inicioPendente ? {
                inicio: competencia < inicioPendente ? competencia : inicioPendente,
                fim: competencia > inicioPendente ? competencia : inicioPendente,
              } : null
              const erro = candidato && (candidato.inicio < minimo || candidato.fim > maximo)
                ? 'O intervalo completo deve estar dentro da base.'
                : candidato ? validar?.(candidato) : null
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
                  title={erro ?? undefined}
                  disabled={competencia < minimo || competencia > maximo || Boolean(erro)}
                  onClick={() => selecionar(competencia)}
                >
                  {mes.slice(0, 3)}
                </button>
              )
            })}
          </div>
          {mesesFixos === undefined && <p
            id={`${id}-ajuda`}
            className="dashboard-period-help"
            aria-live="polite"
          >
            {inicioPendente
              ? `${formatarMes(inicioPendente)} selecionado. Escolha o mês final habilitado.`
              : `Clique no mês inicial e depois no final. Para um único mês, clique duas vezes nele.`}
          </p>}
        </div>
      )}
    </div>
  )
}
