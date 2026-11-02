// Proposta de contrato da Análise de Receita, a ser servida pelo backend a partir da A3 (fato_segmento_mensal)
// ou da A4 (receita_decomposicao) quando os períodos forem os do diagnóstico. Valores em R$ (receita sem
// tributos, `valor_energia`) e kWh. Nulo = indisponível, nunca zero.
import type { AgruparPor, ClasseConsumo, Periodo } from '../../api/types'

export type AgrupamentoReceita = AgruparPor
export type FonteReceita = 'receita_decomposicao' | 'fato_segmento_mensal'

export type LinhaReceita = {
  /** Identificador estável: município, município + bairro ou classe. */
  chave: string
  rotulo: string
  municipio: string | null
  bairro: string | null
  classe: ClasseConsumo | null
  receita_base: number
  receita_atual: number
  variacao_receita: number
  variacao_receita_pct: number | null
  energia_base_kwh: number
  energia_atual_kwh: number
  variacao_energia_pct: number | null
  /** Nulo quando o período não tem volume (regra de volume zero da A4). */
  preco_base_kwh: number | null
  preco_atual_kwh: number | null
  efeito_volume: number
  efeito_preco: number
  qtd_ucs_base: number
  qtd_ucs_atual: number
}

export type FatoresReceita = {
  /** UCs com GD conectada até o fim do período atual (regra "GD no mês"). */
  qtd_ucs_com_gd: number
  /** Volume dessas mesmas UCs em cada período: a diferença é a queda associada à GD. */
  energia_ucs_gd_base_kwh: number
  energia_ucs_gd_atual_kwh: number
  qtd_trocas_medidor_atual: number
  pct_faturas_bandeira_nao_verde_base: number | null
  pct_faturas_bandeira_nao_verde_atual: number | null
}

export type PontoMensalReceita = {
  competencia: string
  receita: number | null
  energia_kwh: number | null
}

export type AnaliseReceita = {
  periodo_base: Periodo
  periodo_atual: Periodo
  agrupar_por: AgrupamentoReceita
  fonte: FonteReceita
  total: LinhaReceita
  /** Ordenadas da maior queda de receita para a maior alta. */
  linhas: LinhaReceita[]
  fatores: FatoresReceita
  serie: PontoMensalReceita[]
}

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
