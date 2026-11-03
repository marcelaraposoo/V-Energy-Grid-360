import { useId } from 'react'
import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import './portal.css'

type InfoTipProps = {
  /** Nome do que está sendo explicado, para o rótulo acessível ("Sobre: …"). */
  titulo: string
  children: ReactNode
  /** O balão abre para a esquerda (padrão, para o canto direito do card) ou para a direita. */
  alinhar?: 'direita' | 'esquerda'
}

// Explicação de método ou definição, fora do texto principal: abre ao passar o mouse ou ao focar (teclado e toque).
export function InfoTip({ titulo, children, alinhar = 'direita' }: InfoTipProps) {
  const id = useId()
  return (
    <span className={`info-tip info-tip--${alinhar}`}>
      <button type="button" className="info-tip-botao" aria-label={`Sobre: ${titulo}`} aria-describedby={id}>
        <Info size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      <span role="tooltip" id={id} className="info-tip-balao">{children}</span>
    </span>
  )
}
