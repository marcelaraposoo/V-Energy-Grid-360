import type { PerguntaIa } from '../../api/types'

function novoIdentificador(): string {
  return globalThis.crypto?.randomUUID?.() ?? `sessao-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

// Uma instância por montagem da conversa, sem persistência entre páginas/abas.
export function criarSessaoConversa() {
  let id = novoIdentificador()
  return {
    get id() { return id },
    novaConversa() { id = novoIdentificador() },
    pergunta(texto: string): PerguntaIa { return { pergunta: texto, sessao_id: id } },
    aceitaResposta(sessaoDoPedido: string) { return id === sessaoDoPedido },
  }
}
