import { Construction } from 'lucide-react'
import { EmptyState } from './EmptyState'
import { PageHeader } from './PageHeader'

type UnderDevelopmentPageProps = {
  eyebrow: string
  title: string
}

export function UnderDevelopmentPage({
  eyebrow,
  title,
}: UnderDevelopmentPageProps) {
  return (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        description="Esta funcionalidade estará disponível em breve."
      />
      <section className="panel">
        <EmptyState
          icon={Construction}
          title="Em desenvolvimento"
          description="Estamos preparando esta página. Volte em breve para acompanhar as novidades."
        />
      </section>
    </>
  )
}
