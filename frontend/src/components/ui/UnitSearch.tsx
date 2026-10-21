import { useState } from 'react'
import { Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

type UnitSearchProps = {
  compact?: boolean
}

export function UnitSearch({ compact = false }: UnitSearchProps) {
  const [value, setValue] = useState('')
  const navigate = useNavigate()

  return (
    <form
      className={`unit-search${compact ? ' unit-search--compact' : ''}`}
      role="search"
      aria-label={
        compact
          ? 'Busca global de unidade consumidora'
          : 'Buscar unidade consumidora'
      }
      onSubmit={(event) => {
        event.preventDefault()
        if (!value.trim()) return
        navigate(`/uc/${encodeURIComponent(value.trim())}`)
        setValue('')
      }}
    >
      <Search size={18} aria-hidden="true" />
      <input
        id={compact ? 'global-uc-search' : 'page-uc-search'}
        aria-label="Identificador da unidade consumidora"
        placeholder={compact ? 'Buscar UC...' : 'Digite o identificador da UC'}
        value={value}
        onChange={(event) => setValue(event.target.value)}
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
  )
}
