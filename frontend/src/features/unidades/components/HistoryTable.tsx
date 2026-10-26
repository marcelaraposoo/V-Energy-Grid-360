import type { LucideIcon } from 'lucide-react'
import { EmptyState } from '../../../components/ui/EmptyState'

type HistoryTableProps = {
  title: string
  columns: readonly string[]
  icon: LucideIcon
  description: string
  children?: ReactNode
  empty: boolean
}

export function HistoryTable({
  title,
  columns,
  icon,
  description,
  children,
  empty,
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
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr>
              {columns.map((column) => (
                <th scope="col" key={column}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
      {empty && (
        <EmptyState
          compact
          icon={icon}
          title="Nenhum registro disponível"
          description={description}
        />
      )}
    </div>
  )
}
import type { ReactNode } from 'react'
