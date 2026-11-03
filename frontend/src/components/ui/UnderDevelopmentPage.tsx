import { Construction } from 'lucide-react'
import { EmptyState } from './EmptyState'
import { PageHeader } from './PageHeader'

type UnderDevelopmentPageProps = {
  title: string
}

export function UnderDevelopmentPage({
  title,
}: UnderDevelopmentPageProps) {
  return (
    <>
      <PageHeader
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
