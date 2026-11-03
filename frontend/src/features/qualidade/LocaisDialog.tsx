import { useEffect, useId, useRef } from 'react'
import { ArrowLeft, MapPin, UsersRound, X, ZapOff } from 'lucide-react'
import type { LocalInterrupcao } from '../../api/types'
import { horasImpacto, pct, quantidade } from './formatacao'
import '../../components/ui/portal.css'

// Lista completa dos locais. Fecha pelo botão, pela tecla Esc ou ao clicar fora.
export function LocaisDialog({ aberto, locais, porBairro, onFechar, onMunicipio, onVoltar, carregando = false }: {
  aberto: boolean
  locais: LocalInterrupcao[]
  porBairro: boolean
  onFechar: () => void
  onMunicipio?: (municipio: string) => void
  onVoltar?: () => void
  carregando?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const listaRef = useRef<HTMLOListElement>(null)
  const tituloRef = useRef<HTMLHeadingElement>(null)
  const nivelAnterior = useRef(porBairro)
  const id = useId()
  useEffect(() => {
    const dialogo = ref.current
    if (aberto && !dialogo?.open) dialogo?.showModal()
    if (!aberto && dialogo?.open) dialogo.close()
  }, [aberto])
  useEffect(() => {
    if (aberto && nivelAnterior.current !== porBairro) {
      listaRef.current?.scrollTo({ top: 0 })
      tituloRef.current?.focus({ preventScroll: true })
    }
    nivelAnterior.current = porBairro
  }, [aberto, porBairro])
  const filtrar = !porBairro && onMunicipio
  const maior = Math.max(1, ...locais.map((local) => local.horas))

  return (
    <dialog ref={ref} className="dialog qualidade-locais-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={(event) => { if (event.target === event.currentTarget) event.currentTarget.close() }}>
      {aberto && <div className="qualidade-locais-dialog-conteudo">
        <header>
          <div className="qualidade-locais-dialog-titulo">
            <span className="qualidade-locais-dialog-icone"><MapPin size={20} aria-hidden="true" /></span>
            <div>
              <h2 id={id} ref={tituloRef} tabIndex={-1}>Locais mais afetados</h2>
              <p>{porBairro ? 'Bairros' : 'Municípios'} em ordem de impacto no período analisado</p>
            </div>
          </div>
          <button type="button" className="icon-button" aria-label="Fechar lista de locais" onClick={() => ref.current?.close()}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        <div className="qualidade-locais-dialog-legenda">
          <span><i aria-hidden="true" /> Horas sem energia</span>
          <span>{quantidade(locais.length)} {porBairro ? 'bairros' : 'municípios'}</span>
        </div>
        <ol ref={listaRef} className="qualidade-locais-dialog-lista" inert={carregando} aria-busy={carregando}
          aria-label={`Interrupções por ${porBairro ? 'bairro' : 'município'}`}>
          {locais.map((l) => {
            const conteudo = <>
              <span className="qualidade-locais-dialog-local">
                <span className="qualidade-barra-cabecalho">
                  <span className="qualidade-barra-nome">{l.bairro ?? l.municipio}{l.bairro && <small>{l.municipio}</small>}</span>
                  <span className="qualidade-locais-dialog-horas">
                    <strong>{horasImpacto(l.horas)}<span className="sr-only"> sem energia</span></strong>
                    {l.pct_horas !== null && <small>{pct(l.pct_horas)} do total</small>}
                  </span>
                </span>
                <span className="qualidade-barra-trilho" aria-hidden="true">
                  <span className="qualidade-barra qualidade-barra--local" style={{ width: `${(l.horas / maior) * 100}%` }} />
                </span>
                <span className="qualidade-locais-dialog-detalhes">
                  <span><UsersRound size={13} aria-hidden="true" />
                    <span>{quantidade(l.qtd_ucs_afetadas)} de {quantidade(l.qtd_ucs)} UCs afetadas{l.pct_ucs_afetadas !== null && ` (${pct(l.pct_ucs_afetadas)})`}</span>
                  </span>
                  <span><ZapOff size={13} aria-hidden="true" />{quantidade(l.qtd_interrupcoes)} interrupções</span>
                </span>
              </span>
            </>
            return <li key={`${l.municipio}-${l.bairro ?? ''}`}>
              {filtrar
                ? <button type="button" className="qualidade-locais-dialog-item qualidade-locais-dialog-item--botao"
                  disabled={carregando} onClick={() => onMunicipio(l.municipio)}>
                  {conteudo}<span className="sr-only">Filtrar por este município</span>
                </button>
                : <div className="qualidade-locais-dialog-item">{conteudo}</div>}
            </li>
          })}
        </ol>
        <footer className="qualidade-locais-dialog-rodape">
          {onVoltar && <button type="button" className="button button--secondary qualidade-locais-voltar"
            onClick={onVoltar} disabled={carregando} aria-label="Voltar ao recorte anterior" title="Voltar">
            <ArrowLeft size={16} aria-hidden="true" />
          </button>}
          <span role="status">{carregando ? 'Atualizando locais…'
            : filtrar ? 'Selecione um município para filtrar a tela.' : 'Do maior para o menor total de horas sem energia.'}</span>
        </footer>
      </div>}
    </dialog>
  )
}
