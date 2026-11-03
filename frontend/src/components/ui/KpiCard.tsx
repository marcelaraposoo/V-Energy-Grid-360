import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { tendencia, variacao as formatarVariacao } from '../../utils/indicadores'
import { InfoTip } from './InfoTip'
import './kpi.css'

type KpiCardProps = {
  titulo: string
  icone: LucideIcon
  /** Valor já formatado; "—" quando indisponível. */
  valor: string
  info?: ReactNode
  /** Valor e período da referência, já formatados. Sem referência, o card não mostra comparação. */
  referencia?: { valor: string; periodo: string } | null
  /** Variação % contra a referência; nula quando não há dado nos dois lados. */
  variacao?: number | null
  /** Pinta a variação (verde sobe, vermelho cai). Desligado para o preço, bom para a receita e ruim para o cliente. */
  colorir?: boolean
  /** Cor do próprio valor, para cards cujo valor já é uma variação. */
  tendenciaValor?: 'favoravel' | 'desfavoravel'
  /** Substitui as linhas de referência e comparação. */
  children?: ReactNode
}

// Card de KPI comum ao Dashboard e à Análise de Receita.
export function KpiCard({ titulo, icone: Icone, valor, info, referencia, variacao = null, colorir = true, tendenciaValor, children }: KpiCardProps) {
  const Seta = variacao === null || variacao === 0 ? Minus : variacao < 0 ? ArrowDownRight : ArrowUpRight
  return (
    <article className="panel kpi-card">
      <header className="kpi-card-cabecalho">
        <h2><Icone size={17} strokeWidth={1.5} aria-hidden="true" />{titulo}</h2>
        {info && <InfoTip titulo={titulo}>{info}</InfoTip>}
      </header>
      <p className="kpi-card-valor" data-tendencia={tendenciaValor}>{valor}</p>
      {children ?? (referencia && <>
        <p className="kpi-card-referencia">Referência: {referencia.valor}</p>
        <p className="kpi-comparacao" title={`Referência: ${referencia.periodo}`}>
          {variacao !== null
            ? <><span data-tendencia={colorir ? tendencia(variacao) : undefined}><Seta size={15} aria-hidden="true" />{formatarVariacao(variacao)}</span></>
            : 'Sem dados para comparação'}
        </p>
      </>)}
    </article>
  )
}
