// Camada HTTP mínima (fetch puro, sem dependências): monta a URL, trata erros e lê JSON.

export type Query = Record<string, string | number | boolean | null | undefined>

export type RequestOptions = {
  params?: Query
  body?: unknown
  signal?: AbortSignal
}

export type HttpResponse<T> = { data: T; headers: Headers }

// Erro lançado em qualquer resposta que não seja 2xx (status 0 = não conseguiu falar com o servidor).
// `detail` já vem em texto legível, pronto para mostrar ao usuário.
export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

type FastApiDetail =
  | string
  | { loc?: (string | number)[]; msg?: string }[]
  | undefined

function legivel(detail: FastApiDetail, status: number): string {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // Erro de validação (422): "campo: mensagem"
    return detail
      .map((d) => {
        const campo = (d.loc ?? []).filter((p) => p !== 'query' && p !== 'body').join('.')
        return campo ? `${campo}: ${d.msg ?? 'valor inválido'}` : (d.msg ?? 'valor inválido')
      })
      .join('; ')
  }
  return `Erro ${status} ao consultar o servidor`
}

export function montarQuery(params?: Query): string {
  if (!params) return ''
  const qs = new URLSearchParams()
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === null || valor === '') continue
    qs.set(chave, String(valor))
  }
  const texto = qs.toString()
  return texto ? `?${texto}` : ''
}

export function createHttp(baseUrl: string, fetchImpl: typeof fetch = fetch) {
  const base = baseUrl.replace(/\/+$/, '')

  async function request<T>(
    method: 'GET' | 'POST' | 'DELETE',
    path: string,
    { params, body, signal }: RequestOptions = {},
  ): Promise<HttpResponse<T>> {
    let resposta: Response
    try {
      resposta = await fetchImpl(`${base}${path}${montarQuery(params)}`, {
        method,
        signal,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (erro) {
      if (signal?.aborted) throw erro // cancelamento é esperado: quem chamou decide o que fazer
      throw new ApiError(0, `Não foi possível conectar ao servidor (${base || 'mesmo endereço'}). Ele está rodando?`)
    }

    if (!resposta.ok) {
      let detail: FastApiDetail
      try {
        detail = ((await resposta.json()) as { detail?: FastApiDetail }).detail
      } catch {
        detail = undefined
      }
      throw new ApiError(resposta.status, legivel(detail, resposta.status))
    }

    if (resposta.status === 204) return { data: undefined as T, headers: resposta.headers }
    return { data: (await resposta.json()) as T, headers: resposta.headers }
  }

  return {
    request,
    get: async <T>(path: string, opts?: RequestOptions) => (await request<T>('GET', path, opts)).data,
    post: async <T>(path: string, opts?: RequestOptions) => (await request<T>('POST', path, opts)).data,
    delete: async <T>(path: string, opts?: RequestOptions) => (await request<T>('DELETE', path, opts)).data,
  }
}

export type Http = ReturnType<typeof createHttp>
