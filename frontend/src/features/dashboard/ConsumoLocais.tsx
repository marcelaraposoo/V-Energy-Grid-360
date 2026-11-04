import { useState } from 'react'
import { MapPinOff } from 'lucide-react'
import type { ConsumoLocaisResponse, Periodo } from '../../api'
import { EmptyState } from '../../components/ui/EmptyState'
import { ConsumoLocaisDialog } from './ConsumoLocaisDialog'
import { VariacaoConsumo } from './VariacaoConsumo'
import { disponivel, formatarPeriodo, kwhCompacto, nomeLocal, participacao } from './formatacao'

// Mesmo número de linhas das cinco classes: o card não muda de altura ao trocar a visão.
const LIMITE_LOCAIS = 5

// Energia por município (distribuidora) ou por bairro (com município escolhido), no estilo das classes.
export function ConsumoLocais({ dados, periodo, referencia, onMunicipio }: {
  dados: ConsumoLocaisResponse
  periodo: Periodo
  referencia: Periodo | null
  onMunicipio?: (municipio: string) => void
}) {
  const [aberto, setAberto] = useState(false)
  const porBairro = dados.nivel === 'bairro'
  const filtrar = !porBairro ? onMunicipio : undefined
  const maximo = Math.max(1, ...dados.locais.map((local) => local.consumo_kwh ?? 0))
  const visiveis = dados.locais.slice(0, LIMITE_LOCAIS)
  const unidade = porBairro ? 'bairros' : 'municípios'
  if (!dados.locais.length) {
    return <EmptyState icon={MapPinOff} title="Sem dados por local" description="Não há dados disponíveis no período selecionado." compact />
  }

  return <div className="dashboard-classes-content">
    <ul className="dashboard-classes-list" aria-label={`Volume de energia faturada por ${porBairro ? 'bairro' : 'município'}`}>
      {visiveis.map((local) => {
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
        </>
        return <li key={`${local.municipio}-${local.bairro ?? ''}`}>
          {filtrar
            ? <button type="button" className="dashboard-class-row" onClick={() => filtrar(local.municipio)}>
              {conteudo}<span className="sr-only">Filtrar o Dashboard por este município</span>
            </button>
            : <div className="dashboard-class-row dashboard-class-row--estatica">{conteudo}</div>}
        </li>
      })}
    </ul>
    <div className="dashboard-classes-note dashboard-locais-rodape">
      <span>
        {dados.locais.length > LIMITE_LOCAIS ? `${visiveis.length} de ${dados.locais.length} ${unidade}` : `${dados.locais.length} ${unidade}`}
        {referencia ? ` · Variação vs. referência · ${formatarPeriodo(referencia)}` : ' · Participação no consumo do período'}
      </span>
      {dados.locais.length > LIMITE_LOCAIS && <button type="button" className="link-button" onClick={() => setAberto(true)}>Mostrar todos</button>}
    </div>
    <ConsumoLocaisDialog aberto={aberto} dados={dados} periodo={periodo} referencia={referencia}
      onFechar={() => setAberto(false)} onMunicipio={filtrar} />
  </div>
}
