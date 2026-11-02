import { ArrowDownRight, ArrowUpRight, Banknote, CircleDollarSign, Minus, Scale, Zap } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Periodo } from '../../api/types'
import { formatarPeriodo } from '../dashboard/formatacao'
import { kwh, reais, reaisComSinal, tarifa, tendencia, variacao } from './formatacao'
import type { LinhaReceita } from './tipos'

type Card = { titulo: string; icone: LucideIcon; atual: string; base: string; variacao: number | null; colorir: boolean }

function Seta({ valor }: { valor: number | null }) {
  const Icone = valor === null || valor === 0 ? Minus : valor < 0 ? ArrowDownRight : ArrowUpRight
  return <Icone size={15} aria-hidden="true" />
}

export function ResumoReceita({ total, referencia }: { total: LinhaReceita; referencia: Periodo }) {
  const cards: Card[] = [
    { titulo: 'Receita de energia', icone: Banknote, atual: reais(total.receita_atual), base: reais(total.receita_base), variacao: total.variacao_receita_pct, colorir: true },
    { titulo: 'Energia faturada', icone: Zap, atual: kwh(total.energia_atual_kwh), base: kwh(total.energia_base_kwh), variacao: total.variacao_energia_pct, colorir: true },
    // Preço sobe para a receita e pesa para o cliente: fica sem cor.
    { titulo: 'Preço médio por kWh', icone: CircleDollarSign, atual: tarifa(total.preco_atual_kwh), base: tarifa(total.preco_base_kwh),
      variacao: total.preco_base_kwh && total.preco_atual_kwh !== null ? (total.preco_atual_kwh / total.preco_base_kwh - 1) * 100 : null, colorir: false },
  ]
  return (
    <section className="receita-resumo" aria-label="Resumo da variação">
      {cards.map((card) => (
        <article className="panel dashboard-kpi" key={card.titulo}>
          <h2><card.icone size={17} strokeWidth={1.5} aria-hidden="true" />{card.titulo}</h2>
          <p className="dashboard-kpi-value">{card.atual}</p>
          <p className="dashboard-kpi-detail">Referência: {card.base}</p>
          <p className="dashboard-kpi-comparison" title={`Referência: ${formatarPeriodo(referencia)}`}>
            <span data-tendencia={card.colorir ? tendencia(card.variacao) : undefined}><Seta valor={card.variacao} />{variacao(card.variacao)}</span>vs. referência
          </p>
        </article>
      ))}
      <article className="panel dashboard-kpi receita-resumo-variacao">
        <h2><Scale size={17} strokeWidth={1.5} aria-hidden="true" />Variação da receita</h2>
        <p className="dashboard-kpi-value" data-tendencia={tendencia(total.variacao_receita)}>{reaisComSinal(total.variacao_receita)}</p>
        <dl className="receita-resumo-efeitos">
          <div><dt>Efeito volume</dt><dd data-tendencia={tendencia(total.efeito_volume)}>{reaisComSinal(total.efeito_volume)}</dd></div>
          <div><dt>Efeito preço</dt><dd data-tendencia={tendencia(total.efeito_preco)}>{reaisComSinal(total.efeito_preco)}</dd></div>
        </dl>
      </article>
    </section>
  )
}
