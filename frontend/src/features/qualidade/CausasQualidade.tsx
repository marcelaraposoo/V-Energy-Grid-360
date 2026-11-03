import { useState } from 'react'
import { ArrowLeft, CircleSlash, MapPinOff } from 'lucide-react'
import type { CausaContinuidade, LocalInterrupcao } from '../../api/types'
import { EmptyState } from '../../components/ui/EmptyState'
import { InfoTipContent } from '../../components/ui/InfoTip'
import { Panel } from '../../components/ui/Panel'
import { horasImpacto, nomeCausa, pct, quantidade } from './formatacao'
import { LocaisDialog } from './LocaisDialog'

type Aba = 'causas' | 'locais'
const LIMITE_LOCAIS = 4

// Responde ao "onde priorizar manutenção": por que (causas) e onde (locais) as horas sem energia se concentram.
export function CausasQualidade({ causas, locais = [], nivelLocais = 'municipio', onMunicipio, onVoltar, carregando = false, abaInicial = 'causas' }: {
  causas: CausaContinuidade[]
  locais?: LocalInterrupcao[]
  nivelLocais?: 'municipio' | 'bairro'
  onMunicipio?: (municipio: string) => void
  onVoltar?: () => void
  carregando?: boolean
  abaInicial?: Aba
}) {
  const [aba, setAba] = useState<Aba>(abaInicial)
  const porBairro = nivelLocais === 'bairro'
  return (
    <Panel className="qualidade-causas"
      title={aba === 'causas' ? 'Principais causas' : 'Locais mais afetados'}
      description={aba === 'causas' ? 'Horas sem energia por causa, no período analisado'
        : `Horas sem energia por ${porBairro ? 'bairro' : 'município'}, no período analisado`}
      info={aba === 'causas'
        ? <InfoTipContent resumo="Soma das horas sem energia das ocorrências de cada causa." itens={[
          { rotulo: 'Evitável', texto: 'Causa que a manutenção preventiva pode reduzir, conforme a origem dos dados.' },
        ]} nota="Ocorrências sem causa registrada aparecem como “Não informada”." />
        : <InfoTipContent resumo="Local das UCs que ficaram sem energia." itens={[
          { rotulo: 'UCs afetadas', texto: 'UCs distintas do local com ao menos uma interrupção, sobre as UCs cadastradas nele.' },
          { rotulo: 'Nível', texto: 'Na distribuidora, por município; com município ou alimentador escolhido, por bairro.' },
        ]} nota="Não há DEC por bairro: o DEC do alimentador não vale para cada bairro." />}
      actions={<div className="segmented" role="group" aria-label="Ver">
        <button type="button" className="button button--secondary" aria-pressed={aba === 'causas'} onClick={() => setAba('causas')}>Causas</button>
        <button type="button" className="button button--secondary" aria-pressed={aba === 'locais'} onClick={() => setAba('locais')}>Locais</button>
      </div>}>
      {aba === 'causas' ? <Causas causas={causas} /> : <Locais locais={locais} porBairro={porBairro}
        onMunicipio={onMunicipio} onVoltar={onVoltar} carregando={carregando} />}
    </Panel>
  )
}

function Causas({ causas }: { causas: CausaContinuidade[] }) {
  if (!causas.length) return <EmptyState icon={CircleSlash} title="Nenhuma interrupção" description="Não há ocorrências no recorte selecionado." compact />
  const maior = causas[0]?.horas || 1
  const evitaveis = causas.filter((c) => c.causa_evitavel).reduce((soma, c) => soma + (c.pct_horas ?? 0), 0)
  return <>
    <p className="qualidade-causas-destaque">
      <strong>{pct(evitaveis)}</strong> das horas sem energia vieram de causas evitáveis.
    </p>
    <ol className="qualidade-barras">
      {causas.map((c) => (
        <li key={`${c.causa}-${c.causa_evitavel}`} className="qualidade-barra-item">
          <span className="qualidade-barra-cabecalho">
            <span className="qualidade-barra-nome">
              {nomeCausa(c.causa)}
              {c.causa_evitavel && <span className="badge qualidade-evitavel">Evitável</span>}
            </span>
            <span className="qualidade-barra-valor">
              {horasImpacto(c.horas)}<small>{c.pct_horas === null ? '' : pct(c.pct_horas)} · {quantidade(c.qtd_interrupcoes)} ocorrências</small>
            </span>
          </span>
          <span className="qualidade-barra-trilho" aria-hidden="true">
            <span className="qualidade-barra" data-evitavel={c.causa_evitavel} style={{ width: `${(c.horas / maior) * 100}%` }} />
          </span>
        </li>
      ))}
    </ol>
  </>
}

function Locais({ locais, porBairro, onMunicipio, onVoltar, carregando }: {
  locais: LocalInterrupcao[]
  porBairro: boolean
  onMunicipio?: (municipio: string) => void
  onVoltar?: () => void
  carregando: boolean
}) {
  const [aberto, setAberto] = useState(false)
  const primeiro = locais[0]
  const maior = primeiro?.horas || 1
  const visiveis = locais.slice(0, LIMITE_LOCAIS)
  return <>
    {primeiro?.pct_horas != null && <p className="qualidade-causas-destaque">
      <strong>{pct(primeiro.pct_horas)}</strong> das horas sem energia em {primeiro.bairro ?? primeiro.municipio}.
    </p>}
    {!locais.length ? <EmptyState icon={MapPinOff} title="Nenhuma interrupção" description="Não há ocorrências no recorte selecionado." compact /> : <ol className="qualidade-barras">
      {visiveis.map((l) => {
        const conteudo = <>
          <span className="qualidade-barra-cabecalho">
            <span className="qualidade-barra-nome">{l.bairro ?? l.municipio}{l.bairro && <small>{l.municipio}</small>}</span>
            <span className="qualidade-barra-valor">
              {horasImpacto(l.horas)}<small>{l.pct_horas === null ? '' : pct(l.pct_horas)}</small>
            </span>
          </span>
          <span className="qualidade-barra-trilho" aria-hidden="true">
            <span className="qualidade-barra qualidade-barra--local" style={{ width: `${(l.horas / maior) * 100}%` }} />
          </span>
          <span className="qualidade-barra-detalhe">
            {quantidade(l.qtd_ucs_afetadas)} de {quantidade(l.qtd_ucs)} UCs afetadas{l.pct_ucs_afetadas !== null && ` (${pct(l.pct_ucs_afetadas)})`}
            {' · '}{quantidade(l.qtd_interrupcoes)} ocorrências
          </span>
        </>
        const chave = `${l.municipio}-${l.bairro ?? ''}`
        return <li key={chave}>
          {!porBairro && onMunicipio
            ? <button type="button" className="qualidade-barra-item qualidade-barra-item--botao" onClick={() => onMunicipio(l.municipio)}
              aria-label={`${l.municipio}: ${horasImpacto(l.horas)} sem energia. Filtrar por este município.`}>{conteudo}</button>
            : <div className="qualidade-barra-item">{conteudo}</div>}
        </li>
      })}
    </ol>}
    {(locais.length > LIMITE_LOCAIS || onVoltar) && <div className="table-footer qualidade-causas-rodape">
      <div className="qualidade-locais-resumo">
        {onVoltar && <button type="button" className="button button--secondary qualidade-locais-voltar"
          onClick={onVoltar} disabled={carregando} aria-label="Voltar ao recorte anterior" title="Voltar">
          <ArrowLeft size={16} aria-hidden="true" />
        </button>}
        {locais.length > LIMITE_LOCAIS && <span>Exibindo <strong>{visiveis.length}</strong> de <strong>{locais.length}</strong> {porBairro ? 'bairros' : 'municípios'}</span>}
      </div>
      {locais.length > LIMITE_LOCAIS && <button type="button" className="link-button" onClick={() => setAberto(true)}>Mostrar todos</button>}
    </div>}
    <LocaisDialog aberto={aberto} locais={locais} porBairro={porBairro} onFechar={() => setAberto(false)}
      onMunicipio={onMunicipio} onVoltar={onVoltar} carregando={carregando} />
  </>
}
