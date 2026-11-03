import type { ReactNode } from 'react'
import { InfoTip } from './InfoTip'

type PanelProps = {
  title: string
  description?: string
  actions?: ReactNode
  /** Explicação de método ou definição, mostrada no "i" do canto do painel. */
  info?: ReactNode
  /** Posição do ícone de informação; por padrão, junto às ações. */
  infoPosition?: 'title' | 'actions'
  className?: string
  children: ReactNode
}

export function Panel({
  title,
  description,
  actions,
  info,
  infoPosition = 'actions',
  className = '',
  children,
}: PanelProps) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <div>
          <h2 className={info && infoPosition === 'title' ? 'panel-title-with-info' : undefined}>
            {title}
            {info && infoPosition === 'title' && <InfoTip titulo={title} alinhar="esquerda">{info}</InfoTip>}
          </h2>
          {description && <p>{description}</p>}
        </div>
        {info && infoPosition === 'actions' ? (
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
