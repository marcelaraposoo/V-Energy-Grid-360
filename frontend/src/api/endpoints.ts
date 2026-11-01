// Uma função por rota do backend. Convenção: o último argumento é sempre um AbortSignal opcional,
// o que permite cancelar a chamada quando a tela é fechada (o hook useApi já faz isso sozinho).
// Os nomes dos parâmetros são os mesmos da API (snake_case): veja http://localhost:8000/docs.
import type { Http } from './http.ts'
import { prepararParametrosDashboard } from './dashboardPeriodos.ts'
import type {
  AlimentadorDecFec,
  BuscarUcParams,
  CadastroGdResponse,
  CatalogoFiltros,
  ContinuidadeParams,
  ConsumoClassesResponse,
  DashboardParams,
  FilaParams,
  Health,
  Insight,
  KpisResponse,
  NovaOrdem,
  Ordem,
  Pagina,
  PerguntaIa,
  PontoDecFec,
  RespostaIa,
  ResultadoInspecao,
  SeriePonto,
  StatusOrdem,
  SuspeitaFila,
  TelaInsight,
  UnidadeConsumidora,
  VariacaoParams,
  VariacaoResponse,
  Visao360,
} from './types.ts'

export function createApi(http: Http) {
  const id = encodeURIComponent

  return {
    health: (signal?: AbortSignal) => http.get<Health>('/api/health', { signal }),

    filtros: (signal?: AbortSignal) => http.get<CatalogoFiltros>('/api/filtros', { signal }),

    dashboard: {
      kpis: (params: DashboardParams = {}, signal?: AbortSignal) =>
        http.get<KpisResponse>('/api/dashboard/kpis', { params: prepararParametrosDashboard(params), signal }),
      serie: (params: DashboardParams = {}, signal?: AbortSignal) =>
        http.get<SeriePonto[]>('/api/dashboard/serie', { params: prepararParametrosDashboard(params), signal }),
      cadastroGd: (params: DashboardParams = {}, signal?: AbortSignal) =>
        http.get<CadastroGdResponse>('/api/dashboard/cadastro-gd', { params: prepararParametrosDashboard(params), signal }),
      consumoClasses: (params: DashboardParams = {}, signal?: AbortSignal) =>
        http.get<ConsumoClassesResponse>('/api/dashboard/consumo-classes', { params: prepararParametrosDashboard(params), signal }),
    },

    receita: {
      variacao: (params: VariacaoParams = {}, signal?: AbortSignal) =>
        http.get<VariacaoResponse>('/api/receita/variacao', { params, signal }),
    },

    unidades: {
      buscar: (params: BuscarUcParams = {}, signal?: AbortSignal) =>
        http.get<UnidadeConsumidora[]>('/api/unidades', { params, signal }),
      visao360: (ucId: string, signal?: AbortSignal) =>
        http.get<Visao360>(`/api/unidades/${id(ucId)}/visao-360`, { signal }),
    },

    perdas: {
      // A lista vem no corpo; o total (após filtros e busca) vem no cabeçalho X-Total-Count.
      fila: async (params: FilaParams = {}, signal?: AbortSignal): Promise<Pagina<SuspeitaFila>> => {
        const { data, headers } = await http.request<SuspeitaFila[]>('GET', '/api/perdas/fila', { params, signal })
        const cabecalho = headers.get('X-Total-Count')
        const total = cabecalho === null ? NaN : Number(cabecalho)
        return { itens: data, total: Number.isFinite(total) ? total : data.length }
      },
      criarOrdem: (ordem: NovaOrdem, signal?: AbortSignal) =>
        http.post<Ordem>('/api/perdas/ordens', { body: ordem, signal }),
      listarOrdens: (status?: StatusOrdem, signal?: AbortSignal) =>
        http.get<Ordem[]>('/api/perdas/ordens', { params: { status }, signal }),
      obterOrdem: (ordemId: number, signal?: AbortSignal) =>
        http.get<Ordem>(`/api/perdas/ordens/${ordemId}`, { signal }),
      iniciarOrdem: (ordemId: number, signal?: AbortSignal) =>
        http.post<Ordem>(`/api/perdas/ordens/${ordemId}/iniciar`, { signal }),
      registrarResultado: (ordemId: number, resultado: ResultadoInspecao, signal?: AbortSignal) =>
        http.post<Ordem>(`/api/perdas/ordens/${ordemId}/resultado`, { body: resultado, signal }),
      cancelarOrdem: (ordemId: number, signal?: AbortSignal) =>
        http.post<Ordem>(`/api/perdas/ordens/${ordemId}/cancelar`, { signal }),
    },

    continuidade: {
      alimentadores: (params: ContinuidadeParams & { municipio?: string } = {}, signal?: AbortSignal) =>
        http.get<AlimentadorDecFec[]>('/api/continuidade/alimentadores', { params, signal }),
      serie: (alimentadorId: string, params: ContinuidadeParams = {}, signal?: AbortSignal) =>
        http.get<PontoDecFec[]>(`/api/continuidade/alimentadores/${id(alimentadorId)}/serie`, { params, signal }),
    },

    ia: {
      perguntar: (pergunta: PerguntaIa, signal?: AbortSignal) =>
        http.post<RespostaIa>('/api/ia/perguntar', { body: pergunta, signal }),
      limparSessao: (sessaoId: string, signal?: AbortSignal) =>
        http.delete<void>(`/api/ia/sessoes/${id(sessaoId)}`, { signal }),
      insights: (tela: TelaInsight, signal?: AbortSignal) =>
        http.get<Insight[]>('/api/ia/insights', { params: { tela }, signal }),
    },
  }
}

export type Api = ReturnType<typeof createApi>
