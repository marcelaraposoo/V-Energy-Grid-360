// Rotas de perdas que não cabem no cliente JSON de `src/api` (download de CSV e upload de planilha).
import { ApiError, montarQuery } from '../../api/http'
import type { Query } from '../../api/http'

const base = (
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'
).replace(/\/+$/, '')

/** Link de download do CSV da fila, com os mesmos filtros da tela. */
export function urlExportarFila(params: Query): string {
  return `${base}/api/perdas/fila/exportar${montarQuery(params)}`
}

/** Link de download do modelo de planilha (ordens em aberto, com colunas de resultado vazias). */
export function urlModeloResultados(): string {
  return `${base}/api/perdas/ordens/resultados/modelo`
}

export type RejeicaoImportacao = { linha: number; ordem_id: number | null; erro: string }
export type ResumoImportacao = {
  total: number
  aceitas: number
  ignoradas: number
  rejeitadas: RejeicaoImportacao[]
}

/** Envia o CSV preenchido pela equipe de campo; o backend registra cada resultado válido. */
export async function importarResultados(arquivo: File): Promise<ResumoImportacao> {
  let resposta: Response
  try {
    resposta = await fetch(`${base}/api/perdas/ordens/resultados/importar`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv' },
      body: await arquivo.arrayBuffer(),
    })
  } catch {
    throw new ApiError(0, `Não foi possível conectar ao servidor (${base}). Ele está rodando?`)
  }
  if (!resposta.ok) {
    let detail = `Erro ${resposta.status} ao enviar a planilha`
    try {
      const corpo = (await resposta.json()) as { detail?: unknown }
      if (typeof corpo.detail === 'string') detail = corpo.detail
    } catch {
      /* mantém a mensagem padrão */
    }
    throw new ApiError(resposta.status, detail)
  }
  return (await resposta.json()) as ResumoImportacao
}
