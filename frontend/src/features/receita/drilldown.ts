// Detalhamento progressivo: município → bairro → classe. Bairro sempre anda junto com o município.
import type { AgrupamentoReceita, FiltrosReceita, LinhaReceita } from './tipos'

export type Recorte = FiltrosReceita & { agrupar_por: AgrupamentoReceita }

export const recorteInicial: Recorte = { municipio: null, bairro: null, classe: null, agrupar_por: 'municipio' }

export type HistoricoRecortes = { atual: Recorte; anteriores: Recorte[] }
type AcaoRecorte = { tipo: 'selecionar'; valor: Recorte } | { tipo: 'voltar' } | { tipo: 'limpar' }

export function alterarRecorte(estado: HistoricoRecortes, acao: AcaoRecorte): HistoricoRecortes {
  if (acao.tipo === 'limpar') return { atual: recorteInicial, anteriores: [] }
  if (acao.tipo === 'voltar') {
    const anterior = estado.anteriores.at(-1)
    return anterior ? { atual: anterior, anteriores: estado.anteriores.slice(0, -1) } : estado
  }
  if (estado.atual.municipio === acao.valor.municipio && estado.atual.bairro === acao.valor.bairro
    && estado.atual.classe === acao.valor.classe && estado.atual.agrupar_por === acao.valor.agrupar_por) return estado
  return { atual: acao.valor, anteriores: [...estado.anteriores, estado.atual] }
}

function agrupamentoPadrao(f: FiltrosReceita): AgrupamentoReceita {
  if (!f.municipio) return 'municipio'
  if (!f.bairro) return 'bairro'
  return 'classe'
}

/** Agrupamentos que geram mais de uma linha para os filtros atuais. */
export function agrupamentosDisponiveis(f: FiltrosReceita): AgrupamentoReceita[] {
  return (['municipio', 'bairro', 'classe'] as const).filter((a) =>
    a === 'municipio' ? !f.municipio : a === 'bairro' ? !f.bairro : !f.classe)
}

export function filtrar(recorte: Recorte, filtros: Partial<FiltrosReceita>): Recorte {
  const f = { ...recorte, ...filtros }
  if (filtros.municipio !== undefined && filtros.bairro === undefined) f.bairro = null
  if (!f.municipio) f.bairro = null
  const disponiveis = agrupamentosDisponiveis(f)
  const padrao = agrupamentoPadrao(f)
  // Mudança territorial leva ao próximo nível; só a classe preserva o agrupamento escolhido, se ainda fizer sentido.
  const agrupar_por = filtros.municipio !== undefined || filtros.bairro !== undefined || !disponiveis.includes(recorte.agrupar_por)
    ? (disponiveis.includes(padrao) ? padrao : disponiveis[0] ?? 'classe') : recorte.agrupar_por
  return { ...f, agrupar_por }
}

/** Próximo nível ao clicar numa linha; nulo quando não há para onde descer. */
export function aprofundar(recorte: Recorte, linha: LinhaReceita): Recorte | null {
  if (recorte.agrupar_por === 'municipio' && linha.municipio) return filtrar(recorte, { municipio: linha.municipio })
  if (recorte.agrupar_por === 'bairro' && linha.municipio && linha.bairro) {
    return filtrar(recorte, { municipio: linha.municipio, bairro: linha.bairro })
  }
  if (recorte.agrupar_por === 'classe' && linha.classe && !recorte.bairro) return filtrar(recorte, { classe: linha.classe })
  return null
}
