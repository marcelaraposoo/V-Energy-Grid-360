import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import './controls.css'

export type Opcao = { value: string; label: string }

type SelectFieldProps = {
  label: string
  value: string
  onChange: (valor: string) => void
  options: Opcao[]
  placeholder?: string
  disabled?: boolean
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder = 'Todos',
  disabled = false,
}: SelectFieldProps) {
  const [aberto, setAberto] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const botaoRef = useRef<HTMLButtonElement>(null)
  const opcoesRef = useRef<(HTMLLIElement | null)[]>([])
  const id = useId()
  const itens = [{ value: '', label: placeholder }, ...options]

  useEffect(() => {
    if (!aberto) return
    const selecionado = containerRef.current
      ?.querySelector<HTMLElement>('[aria-selected="true"]')
    selecionado?.focus({ preventScroll: true })
    selecionado?.scrollIntoView({ block: 'nearest' })
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

  function focarOpcao(indice: number) {
    const opcao = opcoesRef.current[indice]
    opcao?.focus({ preventScroll: true })
    opcao?.scrollIntoView({ block: 'nearest' })
  }

  return (
    <div
      className="filter-field select-picker"
      ref={containerRef}
      onKeyDown={(event) => {
        if (disabled) return
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
          focarOpcao(proximo)
        } else if (aberto && (event.key === 'Home' || event.key === 'End')) {
          event.preventDefault()
          focarOpcao(event.key === 'Home' ? 0 : itens.length - 1)
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
            selecionar(itens[indice].value)
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
        className="filter-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={aberto}
        aria-controls={aberto ? `${id}-list` : undefined}
        aria-labelledby={`${id}-label ${id}-value`}
        onClick={() => setAberto(!aberto)}
      >
        <span id={`${id}-value`}>
          {itens.find((item) => item.value === value)?.label ?? placeholder}
        </span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {aberto && (
        <ul
          id={`${id}-list`}
          className="filter-list"
          role="listbox"
          aria-labelledby={`${id}-label`}
        >
          {itens.map((item, indice) => (
            <li
              key={item.value}
              role="option"
              aria-selected={item.value === value}
              tabIndex={-1}
              ref={(elemento) => {
                opcoesRef.current[indice] = elemento
              }}
              onClick={() => selecionar(item.value)}
            >
              <span>{item.label}</span>
              {item.value === value && <Check size={14} aria-hidden="true" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
