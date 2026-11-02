import type { ClasseConsumo } from '../../api/types'

export const nomesClasse: Record<ClasseConsumo, string> = {
  RESIDENCIAL: 'Residencial', COMERCIAL: 'Comercial', INDUSTRIAL: 'Industrial', 'PODER PUBLICO': 'Poder público', RURAL: 'Rural',
}

const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const compactoComSinal = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const precoKwh = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 4, maximumFractionDigits: 4 })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const percentualSimples = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const reais = (valor: number) => `R$ ${compacto.format(valor)}`
export const reaisComSinal = (valor: number) => `${valor < 0 ? '−' : valor > 0 ? '+' : ''}R$ ${compacto.format(Math.abs(valor))}`
export const reaisCompletos = (valor: number) => moeda.format(valor)
export const kwh = (valor: number) => `${compacto.format(valor)} kWh`
export const kwhComSinal = (valor: number) => `${compactoComSinal.format(valor)} kWh`.replace('-', '−')
export const tarifa = (valor: number | null) => valor === null ? '—' : precoKwh.format(valor)
export const quantidade = (valor: number) => inteiro.format(valor)
export const variacao = (valor: number | null) => valor === null ? '—' : `${percentual.format(valor).replace('-', '−')}%`
export const participacao = (valor: number | null) => valor === null ? '—' : `${percentualSimples.format(valor)}%`

/** Leitura da variação para a receita: subir é favorável, cair é desfavorável. */
export function tendencia(valor: number | null) {
  if (valor === null || valor === 0) return undefined
  return valor > 0 ? 'favoravel' : 'desfavoravel'
}
