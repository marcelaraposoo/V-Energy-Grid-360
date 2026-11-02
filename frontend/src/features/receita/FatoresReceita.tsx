import { Flag, Gauge, Sun } from 'lucide-react'
import { Panel } from '../../components/ui/Panel'
import { kwh, kwhComSinal, participacao, quantidade, reaisComSinal } from './formatacao'
import type { AnaliseReceita } from './tipos'

// Fatores associados à variação: GD nas mesmas UCs (A2), bandeira e troca de medidor (A3).
// São associações medidas nos dados, não causas comprovadas.
export function FatoresReceita({ analise }: { analise: AnaliseReceita }) {
  const { fatores } = analise
  return (
    <Panel title="Fatores associados" description="O que acompanha a variação no recorte selecionado" className="receita-fatores">
      <ul className="receita-fatores-lista">
        <li>
          <span className="receita-fatores-icone" aria-hidden="true"><Sun size={16} strokeWidth={1.6} /></span>
          <div>
            <h3>Geração distribuída</h3>
            <p><strong>{quantidade(fatores.qtd_ucs_com_gd)}</strong> UCs com painel solar conectado até o fim do período.</p>
            <VolumeGd analise={analise} />
          </div>
        </li>
        <li>
          <span className="receita-fatores-icone" aria-hidden="true"><Flag size={16} strokeWidth={1.6} /></span>
          <div>
            <h3>Bandeira tarifária</h3>
            <p>Faturas com bandeira diferente de verde: <strong>{participacao(fatores.pct_faturas_bandeira_nao_verde_base)}</strong> na referência
              {' '}→ <strong>{participacao(fatores.pct_faturas_bandeira_nao_verde_atual)}</strong> no período atual.</p>
            <p>O adicional não vem separado na fatura: o efeito da bandeira está dentro do efeito preço e é estimado.</p>
          </div>
        </li>
        <li>
          <span className="receita-fatores-icone" aria-hidden="true"><Gauge size={16} strokeWidth={1.6} /></span>
          <div>
            <h3>Troca de medidor</h3>
            <p><strong>{quantidade(fatores.qtd_trocas_medidor_atual)}</strong> trocas no período atual.</p>
            <p>No mês da troca, o consumo usa a leitura do medidor novo; o preço por kWh desses meses tende a ficar acima do típico.</p>
          </div>
        </li>
      </ul>
      <p className="receita-nota">Associações medidas nos dados; não indicam, sozinhas, a causa da variação.</p>
    </Panel>
  )
}

// Sem o consumo por UC no banco, os volumes vêm nulos: mostra só a contagem, sem inventar valores.
function VolumeGd({ analise: { fatores, total } }: { analise: AnaliseReceita }) {
  const base = fatores.energia_ucs_gd_base_kwh
  const atual = fatores.energia_ucs_gd_atual_kwh
  if (base === null || atual === null) {
    return <p>O volume dessas UCs não está disponível: a base não tem o consumo por UC.</p>
  }
  const deltaGd = atual - base
  const deltaTotal = total.energia_atual_kwh - total.energia_base_kwh
  const deltaDemais = deltaTotal - deltaGd
  const energiaDemaisBase = total.energia_base_kwh - base
  // Com o volume total e o das UCs com GD em queda: se as demais cresceram, a GD responde por mais que a queda inteira.
  const leitura = deltaTotal >= 0 || deltaGd >= 0 ? null
    : deltaDemais >= 0 && energiaDemaisBase > 0
      ? `Sem a redução das UCs com GD, o volume do recorte teria crescido ${participacao((deltaDemais / energiaDemaisBase) * 100)}.`
      : `A redução das UCs com GD equivale a ${participacao((deltaGd / deltaTotal) * 100)} da queda de volume do recorte.`
  return <>
    <p>Energia faturada dessas mesmas UCs: {kwh(base)} → {kwh(atual)}
      {' '}(<strong>{kwhComSinal(deltaGd)}</strong>, ≈ {reaisComSinal(deltaGd * (total.preco_base_kwh ?? 0))} ao preço da referência).</p>
    <p>Demais UCs: {kwhComSinal(deltaDemais)}{energiaDemaisBase > 0 && ` (${participacao(Math.abs(deltaDemais / energiaDemaisBase) * 100)} ${deltaDemais < 0 ? 'de queda' : 'de alta'})`}.</p>
    {leitura && <p className="receita-fatores-destaque">{leitura}</p>}
  </>
}
