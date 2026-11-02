import { useState } from 'react'
import { Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { normalizarIdentificadorUC } from '../../utils/uc'

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
        navigate(`/uc/${encodeURIComponent(normalizarIdentificadorUC(value))}`)
        setValue('')
      }}
    >
      <Search size={18} aria-hidden="true" />
      <input
        id={compact ? 'global-uc-search' : 'page-uc-search'}
        aria-label="Identificador da unidade consumidora"
        placeholder={compact ? 'Buscar UC...' : 'Ex.: UC100000'}
        value={value}
        onChange={(event) => {
          event.currentTarget.setCustomValidity('')
          setValue(event.target.value.trim().toUpperCase())
        }}
        onInvalid={(event) => {
          event.currentTarget.setCustomValidity(
            event.currentTarget.validity.valueMissing
              ? 'Informe o identificador da UC.'
              : 'Use seis dígitos, com ou sem UC, como 000001 ou UC000001.',
          )
        }}
        pattern="(UC)?[0-9]{6}"
        title="Seis dígitos, com ou sem UC, como 000001 ou UC000001"
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
