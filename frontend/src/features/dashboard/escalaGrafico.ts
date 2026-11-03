export function escalaGrafico(valores: number[]) {
  const maior = Math.max(0, ...valores.filter((valor) => Number.isFinite(valor))) || 1
  const bruto = maior / 5
  const ordem = 10 ** Math.floor(Math.log10(bruto))
  const fator = bruto / ordem
  const passo = (fator <= 1 ? 1 : fator <= 2 ? 2 : fator <= 5 ? 5 : 10) * ordem
  const quantidade = Math.ceil(maior / passo)
  const maximo = Number((quantidade * passo).toPrecision(12))
  const divisor = maximo >= 1e9 ? 1e9 : maximo >= 1e6 ? 1e6 : maximo >= 1e3 ? 1e3 : 1
  const prefixo = divisor === 1e9 ? 'bilhões' : divisor === 1e6 ? 'milhões' : divisor === 1e3 ? 'mil' : ''
  const casas = Math.max(0, -Math.floor(Math.log10(passo / divisor)))
  return {
    maximo, divisor, prefixo, casas,
    marcacoes: Array.from({ length: quantidade + 1 }, (_, i) => Number((i * passo).toPrecision(12))),
  }
}

export type UnidadeGrafico = 'R$' | 'kWh' | 'h' | 'un'

export function unidadeDaEscala(unidade: UnidadeGrafico, prefixo: string) {
  if (unidade === 'h') return prefixo ? `${prefixo} de horas` : 'horas'
  if (unidade === 'un') return prefixo || 'unidades'
  if (!prefixo) return unidade
  if (unidade === 'R$') return `R$ ${prefixo}`
  return `${prefixo}${prefixo === 'mil' ? '' : ' de'} kWh`
}
