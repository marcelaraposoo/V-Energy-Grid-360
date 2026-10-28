import type { ReactNode } from 'react'

type UnidadeFieldsProps = {
  fields: { label: string; value: ReactNode }[]
}

export function UnidadeFields({ fields }: UnidadeFieldsProps) {
  return (
    <dl className="ucv-fields">
      {fields.map(({ label, value }) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value ?? 'Não disponível'}</dd>
        </div>
      ))}
    </dl>
  )
}
