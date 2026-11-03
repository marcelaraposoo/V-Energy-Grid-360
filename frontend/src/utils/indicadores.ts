// Indicadores comuns ao Dashboard e à Análise de Receita: mesma formatação e mesmas explicações nas duas telas.
import type { ClasseConsumo } from '../api/types.ts'

export const nomesClasse: Record<ClasseConsumo, string> = {
  RESIDENCIAL: 'Residencial', COMERCIAL: 'Comercial', INDUSTRIAL: 'Industrial', 'PODER PUBLICO': 'Poder público', RURAL: 'Rural',
}

const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const precoKwh = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

export const reais = (valor: number) => `R$ ${compacto.format(valor)}`
export const kwh = (valor: number) => `${compacto.format(valor)} kWh`
/** Duas casas na exibição; variações são calculadas com o valor sem arredondar. */
export const tarifa = (valor: number | null) => valor === null ? '—' : precoKwh.format(valor)
export const variacao = (valor: number | null) => valor === null ? '—' : `${percentual.format(valor).replace('-', '−')}%`

/** Ótica da receita: subir é favorável, cair é desfavorável. */
export function tendencia(valor: number | null) {
  if (valor === null || valor === 0) return undefined
  return valor > 0 ? 'favoravel' : 'desfavoravel'
}

export const explicacoes = {
  receita: 'Soma do valor da energia faturada no período: sem tributos e com o adicional de bandeira tarifária embutido.',
  energia: 'Soma da energia faturada (kWh) no período.',
  preco: 'Receita de energia ÷ energia faturada do período. É uma razão de somas, não a média dos preços mensais. A variação usa o valor sem arredondar.',
}
