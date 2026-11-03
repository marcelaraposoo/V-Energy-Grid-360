// Formatos próprios da Análise de Receita; os comuns às duas telas vêm de utils/indicadores.
export { kwh, nomesClasse, reais, tarifa, tendencia, variacao } from '../../utils/indicadores.ts'

const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const compactoComSinal = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })
const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const percentualSimples = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const reaisComSinal = (valor: number) => `${valor < 0 ? '−' : valor > 0 ? '+' : ''}R$ ${compacto.format(Math.abs(valor))}`
export const reaisCompletos = (valor: number) => moeda.format(valor)
export const kwhComSinal = (valor: number) => `${compactoComSinal.format(valor)} kWh`.replace('-', '−')
export const quantidade = (valor: number) => inteiro.format(valor)
export const participacao = (valor: number | null) => valor === null ? '—' : `${percentualSimples.format(valor)}%`
