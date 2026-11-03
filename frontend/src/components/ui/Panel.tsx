import type { ReactNode } from 'react'
import { InfoTip } from './InfoTip'

type PanelProps = {
  title: string
  description?: string
  actions?: ReactNode
  /** Explicação de método ou definição, mostrada no "i" do canto do painel. */
  info?: ReactNode
  className?: string
  children: ReactNode
}

export function Panel({
  title,
  description,
  actions,
  info,
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
        {info ? (
          <div className="panel-header-aside">
            {actions}
            <InfoTip titulo={title}>{info}</InfoTip>
          </div>
        ) : actions}
      </header>
      {children}
    </section>
  )
}
