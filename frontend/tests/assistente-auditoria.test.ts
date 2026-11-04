import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer as createHttpServer } from 'node:http'
import react from '@vitejs/plugin-react'
import { createServer } from 'vite'

test('auditoria da resposta mostra pipeline, provedores, cache e persistência', async () => {
  const httpServer = createHttpServer()
  const server = await createServer({ configFile: false, plugins: [react()], optimizeDeps: { noDiscovery: true },
    server: { middlewareMode: true, hmr: { server: httpServer }, watch: null } })
  try {
    const { AuditoriaResposta } = await server.ssrLoadModule('/src/features/assistente/AuditoriaResposta.tsx')
    const auditoria = {
      request_id: 'request-12345678',
      resultado: 'answered',
      etapa_final: 'done',
      duracao_ms: 1532,
      cache_hit: false,
      regeneracoes: 1,
      linhas_retornadas: 12,
      resultado_truncado: false,
      persistencia: 'salva',
      etapas: [
        { codigo: 'C1', nome: 'Validação de entrada', status: 'completed', detalhe: 'Entrada normalizada e aprovada.', duracao_ms: 1 },
        { codigo: 'C4.2', nome: 'Validação de SQL', status: 'completed', detalhe: 'Consulta aprovada pelas regras de segurança SQL.', duracao_ms: null },
        { codigo: 'C7', nome: 'Finalização e persistência da auditoria', status: 'completed', detalhe: 'Registro persistido em portal.db.', duracao_ms: null },
      ],
      tentativas_provedor: [
        { fase: 'sql_generation', provedor: 'gemini', modelo: 'gemini-test', tentativa: 1, iniciada_em: '2026-11-04T12:00:00Z', sucesso: true, latencia_ms: 450, tipo_erro: null },
        { fase: 'synthesis', provedor: 'openrouter', modelo: 'model-test', tentativa: 2, iniciada_em: '2026-11-04T12:00:01Z', sucesso: false, latencia_ms: 700, tipo_erro: 'timeout' },
      ],
    }
    const html = renderToStaticMarkup(createElement(AuditoriaResposta, {
      auditoria, sql: 'SELECT classe FROM dim_uc', fontes: ['dim_uc'],
    }))
    assert.match(html, /Auditoria desta resposta/)
    assert.match(html, /Rastro do pipeline/)
    assert.match(html, /C4\.2/)
    assert.match(html, /Tentativas dos provedores/)
    assert.match(html, /gemini-test/)
    assert.match(html, /timeout/)
    assert.match(html, /Registro salvo em portal\.db/)
    assert.match(html, /dim_uc/)
    assert.match(html, /SELECT classe FROM dim_uc/)
    assert.match(html, /1\.53 s/)
  } finally {
    await server.close()
    httpServer.close()
  }
})
