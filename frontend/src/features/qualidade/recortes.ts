export type RecorteQualidade = { municipio: string | null; alimentador: string | null }
export type HistoricoRecortesQualidade = { atual: RecorteQualidade; anteriores: RecorteQualidade[] }
type AcaoRecorte = { tipo: 'selecionar'; valor: RecorteQualidade } | { tipo: 'voltar' } | { tipo: 'limpar' }

export function alterarRecorteQualidade(estado: HistoricoRecortesQualidade, acao: AcaoRecorte): HistoricoRecortesQualidade {
  if (acao.tipo === 'limpar') return { atual: { municipio: null, alimentador: null }, anteriores: [] }
  if (acao.tipo === 'voltar') {
    const anterior = estado.anteriores.at(-1)
    return anterior ? { atual: anterior, anteriores: estado.anteriores.slice(0, -1) } : estado
  }
  if (estado.atual.municipio === acao.valor.municipio && estado.atual.alimentador === acao.valor.alimentador) return estado
  return { atual: acao.valor, anteriores: [...estado.anteriores, estado.atual] }
}
