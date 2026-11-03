import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Info } from 'lucide-react'
import './portal.css'

type InfoTipProps = {
  /** Nome do que está sendo explicado, para o rótulo acessível ("Sobre: …"). */
  titulo: string
  children: ReactNode
  /** O balão abre para a esquerda (padrão, para o canto direito do card) ou para a direita. */
  alinhar?: 'direita' | 'esquerda'
}

/** Explicação curta, com detalhes opcionais para leitura rápida. */
export function InfoTipContent({ resumo, itens, nota }: {
  resumo: ReactNode
  itens?: { rotulo: string; texto: ReactNode }[]
  nota?: ReactNode
}) {
  return <>
    <span className="info-tip-resumo">{resumo}</span>
    {itens && <span className="info-tip-itens">{itens.map(({ rotulo, texto }) => (
      <span className="info-tip-item" key={rotulo}><strong>{rotulo}</strong><span>{texto}</span></span>
    ))}</span>}
    {nota && <span className="info-tip-nota">{nota}</span>}
  </>
}

// O portal evita cortes em cards com overflow; a posição respeita as bordas da tela.
export function InfoTip({ titulo, children, alinhar = 'direita' }: InfoTipProps) {
  const id = useId()
  const [aberto, setAberto] = useState(false)
  const [destino, setDestino] = useState<Element | null>(null)
  const [posicao, setPosicao] = useState<{ left: number; top: number; seta: number; lado: 'acima' | 'abaixo' } | null>(null)
  const botaoRef = useRef<HTMLButtonElement>(null)
  const balaoRef = useRef<HTMLSpanElement>(null)
  const fecharTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function cancelarFechamento() {
    if (fecharTimer.current !== null) clearTimeout(fecharTimer.current)
  }
  function abrir() {
    cancelarFechamento()
    setDestino(botaoRef.current?.closest('dialog[open]') ?? document.body)
    setAberto(true)
  }
  function fecharDepois() {
    cancelarFechamento()
    fecharTimer.current = setTimeout(() => setAberto(false), 140)
  }

  useEffect(() => () => cancelarFechamento(), [])
  const posicionar = useCallback(() => {
    if (!botaoRef.current || !balaoRef.current) return
    const botao = botaoRef.current.getBoundingClientRect()
    if (botao.bottom < 0 || botao.top > window.innerHeight) { setAberto(false); return }
    const balao = balaoRef.current.getBoundingClientRect()
    const margem = 12
    const acima = window.innerHeight - botao.bottom - margem < balao.height + 10 && botao.top > window.innerHeight - botao.bottom
    const left = Math.max(margem, Math.min(alinhar === 'direita' ? botao.right - balao.width : botao.left, window.innerWidth - balao.width - margem))
    const top = Math.max(margem, Math.min(acima ? botao.top - balao.height - 10 : botao.bottom + 10, window.innerHeight - balao.height - margem))
    setPosicao({ left, top, lado: acima ? 'acima' : 'abaixo', seta: Math.max(18, Math.min(botao.left + botao.width / 2 - left, balao.width - 18)) })
  }, [alinhar])
  useLayoutEffect(() => {
    if (aberto) posicionar()
  }, [aberto, posicionar, titulo, children])

  useEffect(() => {
    if (!aberto) return
    function fora(event: PointerEvent) {
      if (event.target instanceof Node && !botaoRef.current?.contains(event.target) && !balaoRef.current?.contains(event.target)) setAberto(false)
    }
    function tecla(event: KeyboardEvent) { if (event.key === 'Escape') setAberto(false) }
    function rolagem(event: Event) {
      if (!(event.target instanceof Node) || !balaoRef.current?.contains(event.target)) posicionar()
    }
    document.addEventListener('pointerdown', fora)
    document.addEventListener('keydown', tecla)
    document.addEventListener('scroll', rolagem, true)
    window.addEventListener('resize', posicionar)
    return () => {
      document.removeEventListener('pointerdown', fora)
      document.removeEventListener('keydown', tecla)
      document.removeEventListener('scroll', rolagem, true)
      window.removeEventListener('resize', posicionar)
    }
  }, [aberto, posicionar])

  const conteudo = <>
    <span className="info-tip-titulo">{titulo}</span>
    <span className="info-tip-conteudo">{children}</span>
  </>
  return (
    <span className="info-tip" onPointerEnter={(event) => { if (event.pointerType === 'mouse') abrir() }}
      onPointerLeave={(event) => { if (event.pointerType === 'mouse') fecharDepois() }}>
      <button ref={botaoRef} type="button" className="info-tip-botao" aria-label={`Sobre: ${titulo}`} aria-describedby={id}
        onFocus={abrir} onBlur={fecharDepois} onClick={abrir}>
        <Info size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {aberto ? createPortal(
        <span ref={balaoRef} role="tooltip" id={id} className="info-tip-balao" data-lado={posicao?.lado}
          style={{ left: posicao?.left ?? 0, top: posicao?.top ?? 0, visibility: posicao ? 'visible' : 'hidden', '--info-tip-seta': `${posicao?.seta ?? 18}px` } as CSSProperties}
          onPointerEnter={cancelarFechamento} onPointerLeave={fecharDepois}>
          {conteudo}
        </span>, destino ?? document.body,
      ) : <span role="tooltip" id={id} className="info-tip-balao" hidden>{conteudo}</span>}
    </span>
  )
}
