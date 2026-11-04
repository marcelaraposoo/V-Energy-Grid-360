import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer as createHttpServer } from 'node:http'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'

test('pergunta normal envia somente pergunta e sessão, sem sinal de reenvio', async () => {
  let body: unknown
  const api = createApi(createHttp('http://test', async (_url, options) => {
    body = JSON.parse(String(options?.body))
    return new Response(JSON.stringify({ status: 'ok', resposta: 'Fixture.' }))
  }))
  await api.ia.perguntar({ pergunta: 'E no mês anterior?', sessao_id: 's1' })
  assert.deepEqual(body, { pergunta: 'E no mês anterior?', sessao_id: 's1' })
})

test('assistente oferece perguntas normais sem controle de reenvio', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({ configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null } })
  try {
    const { AssistentePage } = await server.ssrLoadModule('/src/features/assistente/AssistentePage.tsx')
    const html = renderToStaticMarkup(createElement(AssistentePage))
    assert.doesNotMatch(html, /Repetir última consulta/)
  } finally {
    await server.close()
    httpServer.close()
  }
})
