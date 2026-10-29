import { CircleAlert } from 'lucide-react'
import { mensagemDeErro } from '../../utils/format'
import './portal.css'

export function LoadingState({ label = 'Carregando dados…' }: { label?: string }) {
  return (
    <div className="feedback" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

type ErrorStateProps = {
  error: unknown
  onRetry?: () => void
  title?: string
}

export function ErrorState({
  error,
  onRetry,
  title = 'Não foi possível carregar os dados',
}: ErrorStateProps) {
  return (
    <div className="feedback feedback--error" role="alert">
      <CircleAlert size={24} strokeWidth={1.5} aria-hidden="true" />
      <strong>{title}</strong>
      <span>{mensagemDeErro(error)}</span>
      {onRetry && (
        <button
          type="button"
          className="button button--secondary button--small"
          onClick={onRetry}
        >
          Tentar novamente
        </button>
      )}
    </div>
  )
}
