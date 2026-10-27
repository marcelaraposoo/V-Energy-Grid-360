// Ponto único de importação da API:  import { api, ApiError } from '../../api'
import { createApi } from './endpoints.ts'
import { createHttp } from './http.ts'

// URL do backend. Em desenvolvimento, o padrão é o uvicorn local; para mudar, crie
// frontend/.env.local com VITE_API_URL=... (veja frontend/.env.example).
const urlDoBackend = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export const api = createApi(createHttp(urlDoBackend))

export { ApiError } from './http.ts'
export { useApi } from './useApi.ts'
export type { ApiState } from './useApi.ts'
export type * from './types.ts'
