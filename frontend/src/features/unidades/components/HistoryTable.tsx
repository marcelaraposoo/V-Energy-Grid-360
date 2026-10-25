import type { LucideIcon } from 'lucide-react'
import { EmptyState } from '../../../components/ui/EmptyState'

type HistoryTableProps = {
  title: string
  columns: readonly string[]
  icon: LucideIcon
  description: string
}

export function HistoryTable({
  title,
  columns,
  icon,
  description,
}: HistoryTableProps) {
  return (
    <div className="ucv-history">
      <div
        className="ucv-table-scroll"
        role="region"
        aria-label={title}
        tabIndex={0}
      >
        <table className="ucv-table">
          <caption className="sr-only">
            {title} — consulta disponível em breve.
          </caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th scope="col" key={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody />
        </table>
      </div>
      <EmptyState
        compact
        icon={icon}
        title="Histórico ainda não disponível"
        description={description}
      />
    </div>
  )
}
