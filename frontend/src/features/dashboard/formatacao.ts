import type { Periodo } from '../../api/types'

const competencia = new Intl.DateTimeFormat('pt-BR', { month: 'short', year: 'numeric', timeZone: 'UTC' })

export function formatarCompetencia(mes: string) {
  return competencia.format(new Date(`${mes}-01T00:00:00Z`)).replace(' de ', '/').replace('.', '')
    .replace(/^./, (letra) => letra.toUpperCase())
}

export function formatarPeriodo(periodo: Periodo) {
  const inicio = formatarCompetencia(periodo.inicio)
  const fim = formatarCompetencia(periodo.fim)
  if (periodo.inicio === periodo.fim) return fim
  return periodo.inicio.slice(0, 4) === periodo.fim.slice(0, 4)
    ? `${inicio.split('/')[0]}–${fim}` : `${inicio}–${fim}`
}

export function disponivel(valor: number | null | undefined): valor is number {
  return typeof valor === 'number' && Number.isFinite(valor)
}

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const nota = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const diferencaNota = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

export const quantidade = (valor: number) => inteiro.format(valor)
/** Chamados: compactos a partir de 10 mil ("88,8 mil"), inteiros abaixo disso. */
export const atendimentos = (valor: number) => valor >= 10_000 ? compacto.format(valor) : inteiro.format(valor)
export const satisfacao = (valor: number) => `${nota.format(valor)} de 5`
/** Diferença da nota em pontos; até 2 pontos fica no singular ("−0,2 ponto"). */
export const pontosNota = (valor: number) =>
  `${diferencaNota.format(valor).replace('-', '−')} ${Math.abs(valor) < 2 ? 'ponto' : 'pontos'}`

const kwhCompactoFormato = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })
const participacaoFormato = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Energia compacta das listas de consumo ("86,4 mi kWh"). */
export const kwhCompacto = (valor: number) => `${kwhCompactoFormato.format(valor)} kWh`
export const participacao = (valor: number) => `${participacaoFormato.format(valor)}%`
export const nomeLocal = (local: { municipio: string; bairro: string | null }) => local.bairro ?? local.municipio
