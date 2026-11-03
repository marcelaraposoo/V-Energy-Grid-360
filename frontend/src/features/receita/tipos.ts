// Tipos da tela sobre o contrato de `GET /api/receita/variacao` (api/types.ts).
import type { AgruparPor, ClasseConsumo, Periodo, VariacaoLinha, VariacaoParams, VariacaoResponse } from '../../api/types'

export type AgrupamentoReceita = AgruparPor
export type LinhaReceita = VariacaoLinha
export type AnaliseReceita = VariacaoResponse

export type FiltrosReceita = {
  municipio: string | null
  bairro: string | null
  classe: ClasseConsumo | null
}

export type ConsultaReceita = FiltrosReceita & {
  periodo: Periodo
  referencia: Periodo
  agrupar_por: AgrupamentoReceita
}

export function parametrosReceita(c: ConsultaReceita): VariacaoParams {
  return {
    base_inicio: c.referencia.inicio, base_fim: c.referencia.fim,
    atual_inicio: c.periodo.inicio, atual_fim: c.periodo.fim,
    municipio: c.municipio ?? undefined, bairro: c.bairro ?? undefined, classe: c.classe ?? undefined,
    agrupar_por: c.agrupar_por,
  }
}
