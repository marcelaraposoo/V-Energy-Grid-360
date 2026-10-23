import { MapPinOff } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui/EmptyState'

export function NotFoundPage() {
  return (
    <section className="panel">
      <EmptyState
        icon={MapPinOff}
        title="Página não encontrada"
        description="O endereço acessado não corresponde a uma página da plataforma."
      >
        <Link className="button button--primary" to="/">
          Voltar ao início
        </Link>
      </EmptyState>
    </section>
  )
}
