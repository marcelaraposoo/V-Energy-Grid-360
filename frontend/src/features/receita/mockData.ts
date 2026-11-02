// Dados fictícios exclusivos da apresentação do layout. Não representam uma consulta à Gold.
// A resposta já segue o formato de `AnaliseReceita`: ao integrar, troca-se apenas a origem.
import type { ClasseConsumo, Periodo } from '../../api/types'
import { deslocarMes, quantidadeMeses } from '../../utils/periodosDashboard.ts'
import { periodosDiagnostico } from './periodos.ts'
import { decompor, variacaoPct } from './decomposicao.ts'
import { nomesClasse } from './formatacao.ts'
import type { AnaliseReceita, ConsultaReceita, LinhaReceita } from './tipos'

const territorios: Record<string, string[]> = {
  Recife: ['Boa Viagem', 'Casa Amarela', 'Espinheiro', 'Madalena', 'Várzea'],
  'Jaboatão dos Guararapes': ['Candeias', 'Cavaleiro', 'Curado', 'Piedade'],
  Olinda: ['Bairro Novo', 'Casa Caiada', 'Rio Doce'],
  Paulista: ['Janga', 'Maranguape I', 'Pau Amarelo'],
  Camaragibe: ['Aldeia', 'Tabatinga'],
}

const perfis: Record<ClasseConsumo, { volume: [number, number]; preco: number; consumoUc: number; gd: number }> = {
  RESIDENCIAL: { volume: [1.4e6, 3.2e6], preco: 0.52, consumoUc: 1900, gd: 0.14 },
  COMERCIAL: { volume: [0.6e6, 1.6e6], preco: 0.55, consumoUc: 7200, gd: 0.1 },
  INDUSTRIAL: { volume: [0.9e6, 2.4e6], preco: 0.46, consumoUc: 60000, gd: 0.04 },
  'PODER PUBLICO': { volume: [0.15e6, 0.4e6], preco: 0.53, consumoUc: 9000, gd: 0.03 },
  RURAL: { volume: [0.1e6, 0.3e6], preco: 0.41, consumoUc: 2600, gd: 0.08 },
}

// Peso de cada mês do ano (jan → dez) no consumo anual.
const sazonalidade = [1.08, 1.1, 1.06, 1.0, 0.95, 0.9, 0.88, 0.9, 0.94, 0.98, 1.04, 1.07]
const somaSazonalidade = sazonalidade.reduce((a, b) => a + b, 0)

type Segmento = {
  municipio: string; bairro: string; classe: ClasseConsumo
  volumeAnualBase: number; volumeAnualAtual: number; precoBase: number; precoAtual: number
  ucsBase: number; ucsAtual: number; ucsGd: number; volumeGdBase: number; volumeGdAtual: number; trocas: number
}

function sorteio(texto: string) {
  let semente = [...texto].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261)
  return () => {
    semente = (semente + 0x6d2b79f5) | 0
    let t = Math.imul(semente ^ (semente >>> 15), 1 | semente)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const segmentos: Segmento[] = Object.entries(territorios).flatMap(([municipio, bairros]) => bairros.flatMap((bairro) => {
  const presenca = sorteio(`${municipio}|${bairro}`)
  const classes: ClasseConsumo[] = ['RESIDENCIAL', 'COMERCIAL']
  if (presenca() > 0.3) classes.push('PODER PUBLICO')
  if (presenca() > 0.6) classes.push('INDUSTRIAL')
  if (municipio === 'Camaragibe') classes.push('RURAL')
  return classes.map((classe) => {
    const r = sorteio(`${municipio}|${bairro}|${classe}`)
    const perfil = perfis[classe]
    const volumeAnualBase = perfil.volume[0] + (perfil.volume[1] - perfil.volume[0]) * r()
    const participacaoGd = perfil.gd * (0.3 + 1.4 * r())
    const volumeGdBase = volumeAnualBase * participacaoGd
    const volumeGdAtual = volumeGdBase * (0.35 + 0.1 * r())
    const volumeAnualAtual = (volumeAnualBase - volumeGdBase) * (0.97 + 0.07 * r()) + volumeGdAtual
    const precoBase = perfil.preco * (0.97 + 0.06 * r())
    const ucsBase = Math.max(1, Math.round(volumeAnualBase / perfil.consumoUc))
    const ucsAtual = Math.round(ucsBase * (1 + 0.04 * r()))
    return {
      municipio, bairro, classe, volumeAnualBase, volumeAnualAtual, precoBase, precoAtual: precoBase * (1.1 + 0.05 * r()),
      ucsBase, ucsAtual, ucsGd: Math.round(ucsAtual * participacaoGd * 0.5), volumeGdBase, volumeGdAtual,
      trocas: Math.round(ucsAtual * (0.08 + 0.1 * r())),
    }
  })
}))

export const catalogoReceitaMock = {
  municipios: Object.entries(territorios).map(([nome, bairros]) => ({ nome, bairros })),
  classes: Object.keys(nomesClasse) as ClasseConsumo[],
}

function meses(periodo: Periodo) {
  return Array.from({ length: quantidadeMeses(periodo) }, (_, i) => deslocarMes(periodo.inicio, i))
}

function fracaoDoAno(periodo: Periodo) {
  return meses(periodo).reduce((soma, mes) => soma + sazonalidade[Number(mes.slice(5)) - 1], 0) / somaSazonalidade
}

function linha(chave: string, rotulo: string, grupo: Segmento[], c: ConsultaReceita, extra: Partial<LinhaReceita>): LinhaReceita {
  const fBase = fracaoDoAno(c.referencia)
  const fAtual = fracaoDoAno(c.periodo)
  const soma = (f: (s: Segmento) => number) => grupo.reduce((total, s) => total + f(s), 0)
  const energiaBase = soma((s) => s.volumeAnualBase * fBase)
  const energiaAtual = soma((s) => s.volumeAnualAtual * fAtual)
  const receitaBase = soma((s) => s.volumeAnualBase * fBase * s.precoBase)
  const receitaAtual = soma((s) => s.volumeAnualAtual * fAtual * s.precoAtual)
  return {
    chave, rotulo, municipio: null, bairro: null, classe: null, ...extra,
    receita_base: receitaBase, receita_atual: receitaAtual, variacao_receita: receitaAtual - receitaBase,
    variacao_receita_pct: variacaoPct(receitaBase, receitaAtual),
    energia_base_kwh: energiaBase, energia_atual_kwh: energiaAtual, variacao_energia_pct: variacaoPct(energiaBase, energiaAtual),
    ...decompor(energiaBase, receitaBase, energiaAtual, receitaAtual),
    qtd_ucs_base: soma((s) => s.ucsBase), qtd_ucs_atual: soma((s) => s.ucsAtual),
  }
}

function pctNaoVerde(periodo: Periodo) {
  return periodo.fim <= '2023-06' ? 0 : 66.5
}

export function analiseReceitaMock(c: ConsultaReceita): AnaliseReceita {
  const selecionados = segmentos.filter((s) => (!c.municipio || s.municipio === c.municipio)
    && (!c.bairro || s.bairro === c.bairro) && (!c.classe || s.classe === c.classe))
  const grupos = new Map<string, Segmento[]>()
  for (const s of selecionados) {
    const chave = c.agrupar_por === 'municipio' ? s.municipio : c.agrupar_por === 'bairro' ? `${s.municipio}|${s.bairro}` : s.classe
    grupos.set(chave, [...(grupos.get(chave) ?? []), s])
  }
  const linhas = [...grupos].map(([chave, grupo]) => {
    const { municipio, bairro, classe } = grupo[0]
    return c.agrupar_por === 'municipio' ? linha(chave, municipio, grupo, c, { municipio })
      : c.agrupar_por === 'bairro' ? linha(chave, bairro, grupo, c, { municipio, bairro })
        : linha(chave, nomesClasse[classe], grupo, c, { classe })
  }).sort((a, b) => a.variacao_receita - b.variacao_receita)
  const fBase = fracaoDoAno(c.referencia)
  const fAtual = fracaoDoAno(c.periodo)
  const mensal = (periodo: Periodo, atual: boolean) => meses(periodo).map((competencia) => {
    const peso = sazonalidade[Number(competencia.slice(5)) - 1] / somaSazonalidade
    const energia = selecionados.reduce((t, s) => t + (atual ? s.volumeAnualAtual : s.volumeAnualBase) * peso, 0)
    const receita = selecionados.reduce((t, s) => t + (atual ? s.volumeAnualAtual * s.precoAtual : s.volumeAnualBase * s.precoBase) * peso, 0)
    return { competencia, energia_kwh: energia, receita }
  })
  const diagnostico = periodosDiagnostico.referencia.inicio === c.referencia.inicio && periodosDiagnostico.referencia.fim === c.referencia.fim
    && periodosDiagnostico.periodo.inicio === c.periodo.inicio && periodosDiagnostico.periodo.fim === c.periodo.fim
  return {
    periodo_base: c.referencia, periodo_atual: c.periodo, agrupar_por: c.agrupar_por,
    fonte: diagnostico ? 'receita_decomposicao' : 'fato_segmento_mensal',
    total: linha('TOTAL', 'Total da seleção', selecionados, c, { municipio: c.municipio, bairro: c.bairro, classe: c.classe }),
    linhas,
    fatores: {
      qtd_ucs_com_gd: selecionados.reduce((t, s) => t + s.ucsGd, 0),
      energia_ucs_gd_base_kwh: selecionados.reduce((t, s) => t + s.volumeGdBase * fBase, 0),
      energia_ucs_gd_atual_kwh: selecionados.reduce((t, s) => t + s.volumeGdAtual * fAtual, 0),
      qtd_trocas_medidor_atual: selecionados.reduce((t, s) => t + Math.round(s.trocas * quantidadeMeses(c.periodo) / 12), 0),
      pct_faturas_bandeira_nao_verde_base: pctNaoVerde(c.referencia),
      pct_faturas_bandeira_nao_verde_atual: pctNaoVerde(c.periodo),
    },
    serie: [...mensal(c.referencia, false), ...mensal(c.periodo, true)],
  }
}

/** Simula a latência da API para exercitar os estados de carregamento. */
export function consultarReceitaMock(c: ConsultaReceita, signal?: AbortSignal): Promise<AnaliseReceita> {
  return new Promise((resolve, reject) => {
    const espera = setTimeout(() => resolve(analiseReceitaMock(c)), 250)
    signal?.addEventListener('abort', () => {
      clearTimeout(espera)
      reject(new DOMException('Consulta cancelada', 'AbortError'))
    })
  })
}
