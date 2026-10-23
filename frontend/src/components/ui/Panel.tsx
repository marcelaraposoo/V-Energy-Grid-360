import type { ReactNode } from 'react'

type PanelProps = {
  title: string
  description?: string
  actions?: ReactNode
  className?: string
  children: ReactNode
}

export function Panel({
  title,
  description,
  actions,
  className = '',
  children,
}: PanelProps) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  )
}
