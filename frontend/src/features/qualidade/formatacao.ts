// Formatação dos indicadores de continuidade (DEC/FEC).
const duasCasas = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const compacto = new Intl.NumberFormat('pt-BR', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const percentual = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export const horas = (valor: number) => `${duasCasas.format(valor)} h`
export const vezes = (valor: number) => duasCasas.format(valor)
export const quantidade = (valor: number) => inteiro.format(valor)
/** Horas sem energia somadas de todas as UCs (UC × h): valores grandes em notação compacta. */
export const horasImpacto = (valor: number) => `${valor >= 10_000 ? compacto.format(valor) : inteiro.format(valor)} h`
export const pct = (valor: number) => `${percentual.format(valor)}%`

/** Variação % contra a referência; nula sem referência positiva. */
export function variacaoPct(atual: number | null | undefined, base: number | null | undefined): number | null {
  if (atual == null || base == null || base <= 0) return null
  return (atual / base - 1) * 100
}

const nomesCausa: Record<string, string> = {
  CLIMATICA: 'Climática',
  SOBRECARGA: 'Sobrecarga',
  VEGETACAO: 'Vegetação',
  TERCEIROS: 'Terceiros',
  'NAO IDENTIFICADA': 'Não identificada',
  'FALHA DE EQUIPAMENTO': 'Falha de equipamento',
}

export function nomeCausa(causa: string | null) {
  if (causa === null) return 'Não informada'
  return nomesCausa[causa] ?? causa.charAt(0) + causa.slice(1).toLowerCase()
}

/** Alimentadores com poucas UCs têm DEC/FEC sensíveis a poucas ocorrências (contrato da Gold, A8). */
export const LIMITE_BASE_PEQUENA = 50
