import { useId, useState } from 'react'
import { ArrowDownRight, ArrowLeft, ArrowRight, ArrowUpRight, Flag, Gauge, Minus, Sun } from 'lucide-react'
import { InfoTip, InfoTipContent } from '../../components/ui/InfoTip'
import { Panel } from '../../components/ui/Panel'
import { kwh, kwhComSinal, participacao, quantidade, reaisComSinal, tendencia, variacao } from './formatacao'
import type { AnaliseReceita } from './tipos'

const paginas = ['Geração distribuída', 'Bandeira tarifária e trocas de medidor']

// Fatores associados à variação: GD nas mesmas UCs (A2), bandeira e troca de medidor (A3).
// São associações medidas nos dados, não causas comprovadas.
export function FatoresReceita({ analise }: { analise: AnaliseReceita }) {
  const [pagina, setPagina] = useState(0)
  const id = useId()
  const anterior = (pagina + paginas.length - 1) % paginas.length
  const proxima = (pagina + 1) % paginas.length
  const { fatores } = analise
  const bandeiraBase = fatores.pct_faturas_bandeira_nao_verde_base
  const bandeiraAtual = fatores.pct_faturas_bandeira_nao_verde_atual
  const diferencaBandeira = bandeiraBase !== null && bandeiraAtual !== null ? bandeiraAtual - bandeiraBase : null
  return (
    <Panel title="Fatores associados" description="O que mudou junto com a receita" className="receita-fatores"
      info="Os números mostram associações nos dados. Sozinhos, não comprovam a causa da variação da receita.">
      <div className="receita-fatores-blocos" id={id} role="group" aria-roledescription="carrossel" aria-label="Fatores associados">
        <section className="receita-fator receita-fator--gd" aria-labelledby="fator-gd-titulo" data-ativo={pagina === 0} aria-hidden={pagina !== 0} inert={pagina !== 0}>
          <header className="receita-fator-cabecalho">
            <span className="receita-fatores-icone" aria-hidden="true"><Sun size={17} strokeWidth={1.6} /></span>
            <h3 id="fator-gd-titulo">Geração distribuída</h3>
            <InfoTip titulo="Geração distribuída">
              <InfoTipContent resumo="Compara o consumo das mesmas unidades nos dois períodos." itens={[
                { rotulo: 'Quais unidades?', texto: 'As que têm geração solar conectada até o fim do período atual.' },
                { rotulo: 'Estimativa em R$', texto: 'A mudança no consumo é valorizada ao preço médio da referência.' },
              ]} nota="A comparação mostra uma associação; não comprova, sozinha, a causa da mudança." />
            </InfoTip>
          </header>
          <p className="receita-fator-base"><strong>{quantidade(fatores.qtd_ucs_com_gd)}</strong> UCs com geração solar no fim do período</p>
          <VolumeGd analise={analise} />
        </section>

        <div className="receita-fatores-pagina-dupla" data-ativo={pagina === 1} aria-hidden={pagina !== 1} inert={pagina !== 1}>
          <section className="receita-fator" aria-labelledby="fator-bandeira-titulo">
            <header className="receita-fator-cabecalho">
              <span className="receita-fatores-icone" aria-hidden="true"><Flag size={17} strokeWidth={1.6} /></span>
              <h3 id="fator-bandeira-titulo">Bandeira tarifária</h3>
              <InfoTip titulo="Bandeira tarifária">
                <InfoTipContent resumo="Participação das faturas com bandeira diferente de verde."
                  nota="O adicional não vem separado nos dados. Seu impacto está no efeito preço e é estimado. A diferença entre participações é expressa em pontos percentuais." />
              </InfoTip>
            </header>
            <p className="receita-fator-base">Faturas com <strong>bandeira não verde</strong></p>
            <div className="receita-fator-bandeiras">
              <ParticipacaoBandeira rotulo="Referência" valor={bandeiraBase} />
              <ArrowRight size={16} className="receita-fator-seta" aria-hidden="true" />
              <ParticipacaoBandeira rotulo="Atual" valor={bandeiraAtual} atual />
            </div>
            {diferencaBandeira !== null && <p className="receita-fator-legenda">
              <strong>{variacao(diferencaBandeira).replace('%', ' p.p.')}</strong> na participação das faturas
            </p>}
          </section>

          <section className="receita-fator receita-fator--medidor" aria-labelledby="fator-medidor-titulo">
            <header className="receita-fator-cabecalho">
              <span className="receita-fatores-icone" aria-hidden="true"><Gauge size={17} strokeWidth={1.6} /></span>
              <h3 id="fator-medidor-titulo">Troca de medidor</h3>
              <InfoTip titulo="Troca de medidor">
                <InfoTipContent resumo="Quantidade de trocas realizadas no período atual."
                  nota="No mês da troca, o consumo considera a leitura do medidor novo. Isso pode afetar o preço médio por kWh." />
              </InfoTip>
            </header>
            <p className="receita-fator-medidores"><strong>{quantidade(fatores.qtd_trocas_medidor_atual)}</strong><span>trocas no período analisado</span></p>
          </section>
        </div>
      </div>
      <nav className="receita-fatores-navegacao" aria-label="Navegar entre fatores">
        <span className="receita-fatores-indicadores" aria-hidden="true">
          {paginas.map((rotulo, i) => <i key={rotulo} data-ativo={pagina === i} />)}
        </span>
        <span className="receita-fatores-pagina" role="status" aria-live="polite">{pagina + 1} de {paginas.length}<span className="sr-only">: {paginas[pagina]}</span></span>
        <span className="receita-fatores-controles">
          <button type="button" className="button button--secondary receita-fatores-seta" aria-controls={id}
            aria-label={`Fator anterior: ${paginas[anterior]}`} title={`Anterior: ${paginas[anterior]}`} onClick={() => setPagina(anterior)}>
            <ArrowLeft size={16} aria-hidden="true" />
          </button>
          <button type="button" className="button button--secondary receita-fatores-seta" aria-controls={id}
            aria-label={`Próximo fator: ${paginas[proxima]}`} title={`Próximo: ${paginas[proxima]}`} onClick={() => setPagina(proxima)}>
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        </span>
      </nav>
    </Panel>
  )
}

function ParticipacaoBandeira({ rotulo, valor, atual = false }: { rotulo: string; valor: number | null; atual?: boolean }) {
  return <div className="receita-fator-participacao" data-atual={atual}>
    <span>{rotulo}</span>
    <strong>{participacao(valor)}</strong>
    {valor === null ? <small>Indisponível</small>
      : <span className="receita-fator-trilho" aria-hidden="true"><span style={{ width: `${valor}%` }} /></span>}
  </div>
}

// Sem o consumo por UC no banco, os volumes vêm nulos: mostra só a contagem, sem inventar valores.
function VolumeGd({ analise: { fatores, total } }: { analise: AnaliseReceita }) {
  const base = fatores.energia_ucs_gd_base_kwh
  const atual = fatores.energia_ucs_gd_atual_kwh
  if (base === null || atual === null) return <p className="receita-fator-indisponivel">Consumo dessas unidades indisponível para comparação.</p>
  if (fatores.qtd_ucs_com_gd === 0) return <p className="receita-fator-indisponivel">Nenhuma unidade com geração solar neste recorte.</p>
  const delta = atual - base
  const percentual = base > 0 ? delta / base * 100 : null
  const Seta = delta < 0 ? ArrowDownRight : delta > 0 ? ArrowUpRight : Minus
  const escala = Math.max(base, atual, 1)
  const demaisBase = total.energia_base_kwh - base
  const demaisAtual = total.energia_atual_kwh - atual
  const deltaDemais = demaisAtual - demaisBase
  const percentualDemais = demaisBase > 0 ? deltaDemais / demaisBase * 100 : null
  const estimativa = total.preco_base_kwh === null ? null : delta * total.preco_base_kwh
  return <>
    <div className="receita-fator-leitura">
      <span>Consumo das mesmas UCs</span>
      <strong className="receita-fator-variacao"><Seta size={15} aria-hidden="true" />{variacao(percentual)}</strong>
    </div>
    <div className="receita-fator-comparacao" aria-label="Consumo das UCs com geração distribuída">
      {[{ rotulo: 'Referência', valor: base }, { rotulo: 'Atual', valor: atual }].map(({ rotulo, valor }) => (
        <div className="receita-fator-barra" key={rotulo} data-atual={rotulo === 'Atual'}>
          <span className="receita-fator-barra-label"><span>{rotulo}</span><strong>{kwh(valor)}</strong></span>
          <span className="receita-fator-trilho" aria-hidden="true"><span style={{ width: `${valor / escala * 100}%` }} /></span>
        </div>
      ))}
    </div>
    <div className="receita-fator-impacto">
      <span>Variação de energia</span><strong>{kwhComSinal(delta)}</strong>
      <span>Estimativa em receita<small>ao preço da referência</small></span>
      <strong data-tendencia={estimativa === null ? undefined : tendencia(estimativa)}>{estimativa === null ? 'Indisponível' : `≈ ${reaisComSinal(estimativa)}`}</strong>
    </div>
    {demaisBase >= 0 && demaisAtual >= 0 && <p className="receita-fator-demais">
      <span>Demais UCs</span><strong>{percentualDemais === null ? kwhComSinal(deltaDemais) : variacao(percentualDemais)}</strong>
    </p>}
  </>
}
