import type { Periodo } from '../../api/types.ts'
import { limitesDashboard, validarPeriodo } from '../../utils/periodosDashboard.ts'
import { periodosDaUrl } from '../receita/periodos.ts'

/** Link para a Qualidade do Serviço com os mesmos períodos e município (as regras de período são as do Dashboard). */
export function linkQualidade(periodo: Periodo, referencia: Periodo | null, municipio: string | null = null): string {
  const busca = new URLSearchParams({ atual_inicio: periodo.inicio, atual_fim: periodo.fim })
  if (referencia) {
    busca.set('base_inicio', referencia.inicio)
    busca.set('base_fim', referencia.fim)
  }
  if (municipio) busca.set('municipio', municipio)
  return `/qualidade?${busca}`
}

/** Períodos da URL; nulo se faltarem ou forem inválidos (aí a tela abre no padrão). A referência é opcional. */
export function periodosQualidadeDaUrl(busca: URLSearchParams): { periodo: Periodo; referencia: Periodo | null } | null {
  const comReferencia = periodosDaUrl(busca)
  if (comReferencia) return comReferencia
  const [inicio, fim] = [busca.get('atual_inicio'), busca.get('atual_fim')]
  if (!inicio || !fim || busca.has('base_inicio') || busca.has('base_fim')) return null
  const periodo = { inicio, fim }
  return validarPeriodo(periodo, 24, limitesDashboard) ? null : { periodo, referencia: null }
}
