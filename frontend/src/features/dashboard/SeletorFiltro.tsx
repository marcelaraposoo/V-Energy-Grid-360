import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

type SeletorFiltroProps = {
  label: string
  valor: string
  opcoes: string[]
  placeholder: string
  desabilitado?: boolean
  onChange: (valor: string) => void
}

export function SeletorFiltro({
  label,
  valor,
  opcoes,
  placeholder,
  desabilitado = false,
  onChange,
}: SeletorFiltroProps) {
  const [aberto, setAberto] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const botaoRef = useRef<HTMLButtonElement>(null)
  const opcoesRef = useRef<(HTMLLIElement | null)[]>([])
  const id = useId()
  const itens = [
    { valor: '', label: placeholder },
    ...opcoes.map((opcao) => ({ valor: opcao, label: opcao })),
  ]

  useEffect(() => {
    if (!aberto) return
    containerRef.current
      ?.querySelector<HTMLElement>('[aria-selected="true"]')
      ?.focus({ preventScroll: true })
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
    botaoRef.current?.focus({ preventScroll: true })
  }

  function selecionar(selecionado: string) {
    onChange(selecionado)
    fechar()
  }

  return (
    <div
      className="dashboard-filter dashboard-select-picker"
      ref={containerRef}
      onKeyDown={(event) => {
        if (desabilitado) return
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          if (!aberto) {
            setAberto(true)
            return
          }
          const indice = opcoesRef.current.findIndex(
            (opcao) => opcao === document.activeElement,
          )
          const direcao = event.key === 'ArrowDown' ? 1 : -1
          const proximo =
            indice < 0
              ? direcao === 1
                ? 0
                : itens.length - 1
              : (indice + direcao + itens.length) % itens.length
          opcoesRef.current[proximo]?.focus({ preventScroll: true })
        } else if (aberto && (event.key === 'Home' || event.key === 'End')) {
          event.preventDefault()
          opcoesRef.current[event.key === 'Home' ? 0 : itens.length - 1]?.focus(
            { preventScroll: true },
          )
        } else if (aberto && event.key === 'Escape') {
          event.preventDefault()
          event.stopPropagation()
          fechar()
        } else if (aberto && (event.key === 'Enter' || event.key === ' ')) {
          const indice = opcoesRef.current.findIndex(
            (opcao) => opcao === document.activeElement,
          )
          if (indice >= 0) {
            event.preventDefault()
            selecionar(itens[indice].valor)
          }
        }
      }}
    >
      <label id={`${id}-label`} htmlFor={id}>
        {label}
      </label>
      <button
        id={id}
        ref={botaoRef}
        type="button"
        className="dashboard-filter-trigger"
        disabled={desabilitado}
        aria-haspopup="listbox"
        aria-expanded={aberto}
        aria-controls={aberto ? `${id}-list` : undefined}
        aria-labelledby={`${id}-label ${id}-value`}
        onClick={() => setAberto(!aberto)}
      >
        <span id={`${id}-value`}>{valor || placeholder}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {aberto && (
        <ul
          id={`${id}-list`}
          className="dashboard-filter-list"
          role="listbox"
          aria-labelledby={`${id}-label`}
        >
          {itens.map((item, indice) => (
            <li
              key={item.valor}
              role="option"
              aria-selected={item.valor === valor}
              tabIndex={-1}
              ref={(elemento) => {
                opcoesRef.current[indice] = elemento
              }}
              onClick={() => selecionar(item.valor)}
            >
              <span>{item.label}</span>
              {item.valor === valor && <Check size={14} aria-hidden="true" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
