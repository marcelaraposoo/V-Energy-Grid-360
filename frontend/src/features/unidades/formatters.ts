const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})
const precoKwh = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
})
const percentual = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})
const notaSatisfacao = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function formatarNumero(valor: number | null | undefined): string {
  return valor == null ? 'Não disponível' : numero.format(valor)
}

export function formatarMoeda(valor: number | null | undefined): string {
  return valor == null ? 'Não disponível' : moeda.format(valor)
}

export function formatarPrecoKwh(valor: number | null | undefined): string {
  return valor == null ? 'Não disponível' : precoKwh.format(valor)
}

export function formatarPercentual(valor: number | null): string {
  return valor === null ? 'Não disponível' : `${percentual.format(valor)}%`
}

export function formatarNotaSatisfacao(valor: number | null): string {
  return valor === null ? 'Não avaliado' : `${notaSatisfacao.format(valor)} / 5`
}

export function formatarCompetencia(valor: string): string {
  const [ano, mes] = valor.split('-')
  return `${mes}/${ano}`
}

export function formatarData(valor: string | null | undefined): string {
  if (!valor) return 'Não disponível'
  const [ano, mes, dia] = valor.split('T')[0].split('-')
  return dia ? `${dia}/${mes}/${ano}` : formatarCompetencia(valor)
}

export function formatarDataHora(valor: string | null): string {
  if (!valor) return 'Não disponível'
  const horario = valor.split('T')[1]?.slice(0, 5)
  return `${formatarData(valor)}${horario ? ` às ${horario}` : ''}`
}
