export const situacoesFatura = { paga: 'Paga', aberta: 'Em aberto', atrasada: 'Atrasada' }
export const faixasAtraso = {
  'EM DIA': 'Em dia',
  'ATE 30 DIAS': 'Até 30 dias de atraso',
  '31 A 90 DIAS': '31 a 90 dias de atraso',
  'MAIS DE 90 DIAS': 'Mais de 90 dias de atraso',
}

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

// A Gold pode chegar ao SQLite como ISO ('2025-07-01T14:30:00') ou com espaço ('2025-07-01 14:30:00').
const SEPARADOR_DATA_HORA = /[T ]/

export function formatarData(valor: string | null | undefined): string {
  if (!valor) return 'Não disponível'
  const [ano, mes, dia] = valor.split(SEPARADOR_DATA_HORA)[0].split('-')
  return dia ? `${dia}/${mes}/${ano}` : formatarCompetencia(valor)
}

export function formatarDataHora(valor: string | null): string {
  if (!valor) return 'Não disponível'
  const horario = valor.split(SEPARADOR_DATA_HORA)[1]?.slice(0, 5)
  return `${formatarData(valor)}${horario ? ` às ${horario}` : ''}`
}

const participacao = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 })
/** Parte de um total (0 a 1) como percentual inteiro: 0,75 → "75%". */
export function formatarParticipacao(valor: number): string {
  return participacao.format(valor)
}

// Valores da Gold chegam em maiúsculas e sem acento; a tela mostra com acentuação.
const rotulos: Record<string, string> = {
  'FALTA DE ENERGIA': 'Falta de energia', FATURA: 'Fatura', 'DANO ELETRICO': 'Dano elétrico', 'LIGACAO NOVA': 'Ligação nova',
  'GERACAO DISTRIBUIDA': 'Geração distribuída', RELIGACAO: 'Religação', VISTORIA: 'Vistoria',
  'INTERRUPCAO PARCIAL': 'Interrupção parcial', 'INTERRUPCAO TOTAL': 'Interrupção total', OSCILACAO: 'Oscilação',
  URGENCIA: 'Urgência', RESSARCIMENTO: 'Ressarcimento', 'APOS PAGAMENTO': 'Após pagamento', SOLICITACAO: 'Solicitação',
  HOMOLOGACAO: 'Homologação', PRAZO: 'Prazo', CREDITOS: 'Créditos', CONTESTACAO: 'Contestação', 'SEGUNDA VIA': 'Segunda via',
  'VALOR ALTO': 'Valor alto', PARCELAMENTO: 'Parcelamento', TELEFONE: 'Telefone', APP: 'App', WHATSAPP: 'WhatsApp',
  SITE: 'Site', PRESENCIAL: 'Presencial', ABERTURA: 'Abertura', ANALISE: 'Análise', DESPACHO: 'Despacho',
  'RETORNO AO CLIENTE': 'Retorno ao cliente', ENCERRAMENTO: 'Encerramento', 'DANO EM EQUIPAMENTO': 'Dano em equipamento',
  SOBRECARGA: 'Sobrecarga', 'FIO PARTIDO': 'Fio partido', CLIMATICA: 'Climática', 'FALHA DE EQUIPAMENTO': 'Falha de equipamento',
  'NAO IDENTIFICADA': 'Não identificada', TERCEIROS: 'Terceiros', VEGETACAO: 'Vegetação',
}

export function formatarRotulo(valor: string | null | undefined): string {
  if (!valor) return 'Não informado'
  return rotulos[valor] ?? valor.charAt(0).toUpperCase() + valor.slice(1).toLowerCase()
}

/** Minutos em texto curto: 45 min, 2 h, 2 h 10 min. */
export function formatarDuracao(minutos: number): string {
  const horas = Math.floor(minutos / 60)
  const resto = Math.round(minutos % 60)
  if (!horas) return `${resto} min`
  return resto ? `${formatarNumero(horas)} h ${resto} min` : `${formatarNumero(horas)} h`
}

/** Tempo de resolução de um chamado: em horas até 48 h; depois, em dias com uma casa. */
export function formatarTempoResolucao(horas: number | null): string {
  if (horas === null) return 'Não disponível'
  if (horas < 48) return `${formatarNumero(Math.round(horas * 10) / 10)} h`
  const dias = Math.round((horas / 24) * 10) / 10
  return `${formatarNumero(dias)} dias`
}
