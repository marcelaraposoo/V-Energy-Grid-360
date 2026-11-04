import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ConsumoLocal, Periodo } from '../../api'
import { variacao as formatarVariacao } from '../../utils/indicadores'
import { disponivel } from './formatacao'

/** Variação contra a referência (energia: subir é favorável), com seta e cor. */
export function VariacaoConsumo({ local, referencia }: { local: ConsumoLocal; referencia: Periodo | null }) {
  const mudanca = referencia && disponivel(local.consumo_kwh) && disponivel(local.consumo_referencia_kwh) ? local.variacao_pct : null
  const Seta = mudanca === 0 ? Minus : disponivel(mudanca) && mudanca < 0 ? ArrowDownRight : ArrowUpRight
  const tendencia = disponivel(mudanca) && mudanca !== 0 ? mudanca > 0 ? 'favoravel' : 'desfavoravel' : undefined
  return <span className="dashboard-class-change" data-tendencia={tendencia}>
    {disponivel(mudanca) ? <><Seta size={13} aria-hidden="true" />{formatarVariacao(mudanca)}</> : '—'}
  </span>
}
