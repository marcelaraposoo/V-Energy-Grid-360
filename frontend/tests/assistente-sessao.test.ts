import assert from 'node:assert/strict'
import test from 'node:test'
import { criarSessaoConversa } from '../src/features/assistente/sessao.ts'
import { createApi } from '../src/api/endpoints.ts'
import { createHttp } from '../src/api/http.ts'

test('várias perguntas enviam a mesma sessão; nova conversa altera o identificador sem DELETE', async () => {
  const requests: { method: string | undefined; body: { pergunta: string; sessao_id: string } }[] = []
  const api = createApi(createHttp('http://test', async (_url, options) => {
    requests.push({ method: options?.method, body: JSON.parse(String(options?.body)) })
    return new Response(JSON.stringify({ status: 'ok', resposta: 'Fixture.' }))
  }))
  const conversa = criarSessaoConversa()
  const primeira = conversa.id
  await api.ia.perguntar(conversa.pergunta('Pergunta A?'))
  await api.ia.perguntar(conversa.pergunta('Pergunta B?'))
  conversa.novaConversa()
  await api.ia.perguntar(conversa.pergunta('Pergunta A?'))
  assert.equal(requests[0].body.sessao_id, primeira)
  assert.equal(requests[1].body.sessao_id, primeira)
  assert.notEqual(requests[2].body.sessao_id, primeira)
  assert.equal(requests[2].body.sessao_id, conversa.id)
  assert.ok(requests.every(r => r.method === 'POST'))
  assert.equal(conversa.aceitaResposta(primeira), false)
})

test('nova montagem após reload ou reabertura começa com outra sessão', () => {
  const antes = criarSessaoConversa()
  const pedidoAntigo = antes.pergunta('Pergunta A?')
  // F5 e reabertura descartam o estado React; o inicializador cria outra instância.
  for (const depois of [criarSessaoConversa(), criarSessaoConversa()]) {
    assert.notEqual(depois.id, antes.id)
    assert.notEqual(depois.pergunta('Pergunta A?').sessao_id, pedidoAntigo.sessao_id)
    assert.equal(depois.aceitaResposta(antes.id), false)
  }
})

test('pedidos pendentes capturam a sessão original e não contaminam nova conversa ou outra aba', async () => {
  const primeira = criarSessaoConversa()
  const outraAba = criarSessaoConversa()
  const pendentes: (() => void)[] = []
  const api = createApi(createHttp('http://test', async () => {
    await new Promise<void>(resolve => pendentes.push(resolve))
    return new Response(JSON.stringify({ status: 'ok', resposta: 'Fixture.' }))
  }))
  const antigo = primeira.pergunta('Pergunta antiga?')
  const outro = outraAba.pergunta('Pergunta de outra aba?')
  const respostas = [api.ia.perguntar(antigo), api.ia.perguntar(outro)]
  primeira.novaConversa()
  pendentes.reverse().forEach(resolve => resolve())
  await Promise.all(respostas)
  assert.equal(primeira.aceitaResposta(antigo.sessao_id!), false)
  assert.equal(primeira.aceitaResposta(outro.sessao_id!), false)
  assert.equal(outraAba.aceitaResposta(outro.sessao_id!), true)
  assert.notEqual(primeira.pergunta('Nova pergunta?').sessao_id, antigo.sessao_id)
})
