import { SelectField } from '../../components/ui/Controls'

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
  desabilitado,
  onChange,
}: SeletorFiltroProps) {
  return (
    <SelectField
      label={label}
      value={valor}
      options={opcoes.map((opcao) => ({ value: opcao, label: opcao }))}
      placeholder={placeholder}
      disabled={desabilitado}
      onChange={onChange}
    />
  )
}
