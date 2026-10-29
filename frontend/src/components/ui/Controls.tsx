import './portal.css'

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
  disabled,
}: SelectFieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(evento) => onChange(evento.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((opcao) => (
          <option key={opcao.value} value={opcao.value}>
            {opcao.label}
          </option>
        ))}
      </select>
    </label>
  )
}
