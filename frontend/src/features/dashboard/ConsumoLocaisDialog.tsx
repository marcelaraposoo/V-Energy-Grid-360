import { useEffect, useId, useRef } from 'react'
import { MapPin, X } from 'lucide-react'
import type { ConsumoLocaisResponse, Periodo } from '../../api'
import { VariacaoConsumo } from './VariacaoConsumo'
import { disponivel, formatarPeriodo, kwhCompacto, nomeLocal, participacao } from './formatacao'
import '../../components/ui/portal.css'

// Lista completa dos locais. Fecha pelo botão, pela tecla Esc ou ao clicar fora.
export function ConsumoLocaisDialog({ aberto, dados, periodo, referencia, onFechar, onMunicipio }: {
  aberto: boolean
  dados: ConsumoLocaisResponse
  periodo: Periodo
  referencia: Periodo | null
  onFechar: () => void
  onMunicipio?: (municipio: string) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const dialogo = ref.current
    if (aberto && !dialogo?.open) dialogo?.showModal()
    if (!aberto && dialogo?.open) dialogo.close()
  }, [aberto])
  const porBairro = dados.nivel === 'bairro'
  const maximo = Math.max(1, ...dados.locais.map((local) => local.consumo_kwh ?? 0))

  function filtrar(municipio: string) {
    ref.current?.close()
    onMunicipio?.(municipio)
  }

  return (
    <dialog ref={ref} className="dialog dashboard-locais-dialog" aria-labelledby={id} onClose={onFechar}
      onClick={(event) => { if (event.target === event.currentTarget) event.currentTarget.close() }}>
      {aberto && <div className="dashboard-locais-dialog-conteudo">
        <header>
          <div className="dashboard-locais-dialog-titulo">
            <span className="dashboard-locais-dialog-icone"><MapPin size={20} aria-hidden="true" /></span>
            <div>
              <h2 id={id}>Energia faturada por {porBairro ? `bairro · ${dados.municipio}` : 'município'}</h2>
              <p>{formatarPeriodo(periodo)}{referencia ? ` · variação vs. ${formatarPeriodo(referencia)}` : ''}</p>
            </div>
          </div>
          <button type="button" className="icon-button" aria-label="Fechar lista de locais" onClick={() => ref.current?.close()}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        <ol className="dashboard-locais-dialog-lista" aria-label={`Energia faturada por ${porBairro ? 'bairro' : 'município'}`}>
          {dados.locais.map((local) => {
            const conteudo = <>
              <span className="dashboard-class-heading">
                <span>{nomeLocal(local)}</span>
                <span className="dashboard-class-volume">{disponivel(local.consumo_kwh) ? kwhCompacto(local.consumo_kwh) : 'Indisponível'}
                  {disponivel(local.participacao_pct) && <small> · {participacao(local.participacao_pct)}</small>}
                </span>
              </span>
              <span className="dashboard-class-measure">
                <span className="dashboard-class-track" aria-hidden="true">
                  <span className="dashboard-class-bar" style={{ width: `${disponivel(local.consumo_kwh) ? local.consumo_kwh / maximo * 100 : 0}%` }} />
                </span>
                {referencia && <VariacaoConsumo local={local} referencia={referencia} />}
              </span>
              {referencia && <span className="dashboard-locais-dialog-referencia">
                Referência: {disponivel(local.consumo_referencia_kwh) ? kwhCompacto(local.consumo_referencia_kwh) : 'indisponível'}
              </span>}
            </>
            return <li key={`${local.municipio}-${local.bairro ?? ''}`}>
              {onMunicipio && !porBairro
                ? <button type="button" className="dashboard-class-row" onClick={() => filtrar(local.municipio)}>
                  {conteudo}<span className="sr-only">Filtrar o Dashboard por este município</span>
                </button>
                : <div className="dashboard-class-row dashboard-class-row--estatica">{conteudo}</div>}
            </li>
          })}
        </ol>
        <footer className="dashboard-locais-dialog-rodape">
          {dados.locais.length} {porBairro ? 'bairros' : 'municípios'}, do maior para o menor consumo.
          {onMunicipio && !porBairro ? ' Selecione um município para filtrar o Dashboard.' : ''}
        </footer>
      </div>}
    </dialog>
  )
}
