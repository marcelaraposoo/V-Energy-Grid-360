import type { Periodo } from '../api/types.ts'

export type LimitesPeriodos = { minimo: string; maximo: string }
export type ModoReferencia = 'ano_anterior' | 'periodo_anterior' | 'personalizado'
export type ModoAutomatico = Exclude<ModoReferencia, 'personalizado'>
export const limitesDashboard: LimitesPeriodos = { minimo: '2022-07', maximo: '2026-06' }
export const periodoInicialDashboard: Periodo = { inicio: '2025-07', fim: '2026-06' }
export const referenciaInicialDashboard: Periodo = { inicio: '2022-07', fim: '2023-06' }
// Fim da base no contrato da Gold: valores em aberto, idades e janelas são medidos até essa data.
export const dataCorteGold = '2026-06-30'

/** '2026-06-30' → '30/06/2026'. */
export function formatarData(iso: string): string {
  const [ano, mes, dia] = iso.slice(0, 10).split('-')
  return `${dia}/${mes}/${ano}`
}

export function indiceMes(mes: string): number {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)) return NaN
  return Number(mes.slice(0, 4)) * 12 + Number(mes.slice(5)) - 1
}

export function deslocarMes(mes: string, quantidade: number): string {
  const indice = indiceMes(mes) + quantidade
  return `${Math.floor(indice / 12).toString().padStart(4, '0')}-${String(indice % 12 + 1).padStart(2, '0')}`
}

export function quantidadeMeses(periodo: Periodo): number {
  return indiceMes(periodo.fim) - indiceMes(periodo.inicio) + 1
}

export function validarPeriodo(periodo: Periodo, maxMeses: number, limites = limitesDashboard): string | null {
  const quantidade = quantidadeMeses(periodo)
  if (!Number.isFinite(quantidade) || quantidade < 1) return 'Selecione um intervalo mensal válido, com início até o fim.'
  if (periodo.inicio < limites.minimo || periodo.fim > limites.maximo) return 'O período deve estar dentro das competências disponíveis na base.'
  if (quantidade > maxMeses) return `Selecione de 1 a ${maxMeses} meses.`
  return null
}

export function validarPeriodosDashboard(
  atual: Periodo, referencia: Periodo | null, comparar: boolean, limites = limitesDashboard,
): string | null {
  const erro = validarPeriodo(atual, comparar ? 12 : 24, limites)
  if (erro) return erro
  if (!comparar) return referencia === null ? null : 'Desative a referência ao continuar sem comparação.'
  if (!referencia) return 'Selecione um período de referência ou desative a comparação.'
  const erroBase = validarPeriodo(referencia, 12, limites)
  if (erroBase) return erroBase
  if (quantidadeMeses(atual) !== quantidadeMeses(referencia)) return 'Os períodos devem ter a mesma quantidade de competências.'
  if (atual.inicio <= referencia.fim && referencia.inicio <= atual.fim) return 'Os períodos não podem se sobrepor.'
  return null
}

export function referenciaAutomatica(atual: Periodo, modo: ModoAutomatico): Periodo {
  const quantidade = quantidadeMeses(atual)
  return modo === 'ano_anterior'
    ? { inicio: deslocarMes(atual.inicio, -12), fim: deslocarMes(atual.fim, -12) }
    : { inicio: deslocarMes(atual.inicio, -quantidade), fim: deslocarMes(atual.inicio, -1) }
}

export function sugerirReferencia(atual: Periodo, limites = limitesDashboard): Periodo | null {
  const candidatas = [
    referenciaAutomatica(atual, 'ano_anterior'),
    referenciaAutomatica(atual, 'periodo_anterior'),
  ]
  return candidatas.find((base) => !validarPeriodosDashboard(atual, base, true, limites)) ?? null
}
