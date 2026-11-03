import type { Periodo } from '../../api/types.ts'
import { referenciaAutomatica, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard.ts'
import type { LimitesPeriodos, ModoAutomatico, ModoReferencia } from '../../utils/periodosDashboard.ts'

export type EstadoPeriodos = {
  periodo: Periodo
  comparar: boolean
  referencia: Periodo | null
  modoReferencia: ModoReferencia
  aviso: string | null
}
export type AcaoPeriodos =
  | { tipo: 'periodo'; valor: Periodo }
  | { tipo: 'referencia'; valor: Periodo }
  | { tipo: 'modo'; valor: ModoAutomatico }
  | { tipo: 'comparar'; valor: boolean }
  | { tipo: 'limpar' }

// Com referência, a tela já abre comparando (no Dashboard: primeiro ano da base, o recorte do diagnóstico).
export function estadoInicial(periodo: Periodo, referencia: Periodo | null = null): EstadoPeriodos {
  return referencia
    ? { periodo, comparar: true, referencia, modoReferencia: 'personalizado', aviso: null }
    : { periodo, comparar: false, referencia: null, modoReferencia: 'ano_anterior', aviso: null }
}

export function alterarPeriodos(
  estado: EstadoPeriodos, acao: AcaoPeriodos, padrao: Periodo, limites: LimitesPeriodos,
  referenciaPadrao: Periodo | null = null,
): EstadoPeriodos {
  if (acao.tipo === 'limpar') return estadoInicial(padrao, referenciaPadrao)
  if (acao.tipo === 'modo') {
    const referencia = referenciaAutomatica(estado.periodo, acao.valor)
    const erro = validarPeriodosDashboard(estado.periodo, referencia, true, limites)
    return erro ? { ...estado, aviso: erro }
      : { ...estado, comparar: true, referencia, modoReferencia: acao.valor, aviso: null }
  }
  if (acao.tipo === 'comparar') {
    if (!acao.valor) return { ...estado, comparar: false, referencia: null, modoReferencia: 'ano_anterior', aviso: null }
    const erro = validarPeriodo(estado.periodo, 12, limites)
    if (erro) return { ...estado, aviso: 'Para ativar a comparação, escolha um período de até 12 meses.' }
    const referencia = sugerirReferencia(estado.periodo, limites)
    const modoReferencia = referencia?.inicio === referenciaAutomatica(estado.periodo, 'ano_anterior').inicio ? 'ano_anterior' : 'periodo_anterior'
    return { ...estado, comparar: referencia !== null, referencia, modoReferencia, aviso: referencia ? null
      : 'Não há sugestão válida de referência. Selecione no calendário ou continue sem comparação.' }
  }
  if (acao.tipo === 'referencia') {
    const erro = validarPeriodosDashboard(estado.periodo, acao.valor, true, limites)
    return erro ? { ...estado, aviso: erro } : { ...estado, comparar: true, referencia: acao.valor, modoReferencia: 'personalizado', aviso: null }
  }
  const erro = validarPeriodo(acao.valor, estado.comparar ? 12 : 24, limites)
  if (erro) return { ...estado, aviso: erro }
  if (!estado.comparar) return { ...estado, periodo: acao.valor, aviso: null }
  if (estado.modoReferencia === 'personalizado'
    && !validarPeriodosDashboard(acao.valor, estado.referencia, true, limites)) {
    return { ...estado, periodo: acao.valor, aviso: null }
  }
  if (estado.modoReferencia !== 'personalizado') {
    const referencia = referenciaAutomatica(acao.valor, estado.modoReferencia)
    const erroReferencia = validarPeriodosDashboard(acao.valor, referencia, true, limites)
    return { ...estado, periodo: acao.valor, referencia: erroReferencia ? null : referencia, comparar: !erroReferencia,
      aviso: erroReferencia ? `A referência ficou indisponível: ${erroReferencia} Selecione outra no calendário ou continue sem comparação.` : null }
  }
  const referencia = sugerirReferencia(acao.valor, limites)
  const modoReferencia = referencia?.inicio === referenciaAutomatica(acao.valor, 'ano_anterior').inicio ? 'ano_anterior' : 'periodo_anterior'
  return { ...estado, periodo: acao.valor, comparar: referencia !== null, referencia, modoReferencia,
    aviso: referencia ? 'A referência foi ajustada porque a seleção anterior ficou incompatível.'
      : 'A referência anterior ficou incompatível. Selecione outra no calendário ou continue sem comparação.' }
}
