import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { RotateCcw, Send, Sparkles } from 'lucide-react'
import { api } from '../../api'
import type { RespostaIa, Visualizacao } from '../../api'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { mensagemDeErro } from '../../utils/format'
import { VisualizacaoChart } from './VisualizacaoChart'
import '../../components/ui/portal.css'

type StatusMensagem = RespostaIa['status'] | 'erro'
type Mensagem = {
  id: number
  papel: 'usuario' | 'assistente'
  texto: string
  status?: StatusMensagem
  sql?: string | null
  visualizacao?: Visualizacao | null
  fontes?: string[]
}

const MAX = 500
const MIN = 3
const SUGESTOES = [
  'Qual bairro mais perdeu volume residencial no último ano?',
  'Quanto a receita comercial cresceu em Jaboatão?',
  'Quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?',
  'Quais alimentadores tiveram o pior DEC nos últimos 12 meses?',
]
const ROTULO: Record<StatusMensagem, string> = {
  ok: 'Resposta com base nos dados',
  nao_sei: 'Sem resposta com os dados disponíveis',
  nao_implementado: 'Assistente ainda não conectado ao backend',
  erro: 'Não foi possível obter a resposta',
}

function novaSessao(): string {
  return globalThis.crypto?.randomUUID?.() ?? `sessao-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function AssistentePage() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([])
  const [texto, setTexto] = useState('')
  const [carregando, setCarregando] = useState(false)
  const sessao = useRef(novaSessao())
  const proximoId = useRef(1)
  const fim = useRef<HTMLDivElement>(null)
  const montado = useRef(true)

  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
    }
  }, [])

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: 'end' })
  }, [mensagens, carregando])

  const tamanho = texto.trim().length
  const valido = tamanho >= MIN && tamanho <= MAX

  function adicionar(m: Omit<Mensagem, 'id'>) {
    setMensagens((atuais) => [...atuais, { ...m, id: proximoId.current++ }])
  }

  async function perguntar(pergunta: string) {
    const limpa = pergunta.trim()
    if (limpa.length < MIN || limpa.length > MAX || carregando) return
    adicionar({ papel: 'usuario', texto: limpa })
    setTexto('')
    setCarregando(true)
    try {
      const r = await api.ia.perguntar({ pergunta: limpa, sessao_id: sessao.current })
      if (!montado.current) return
      adicionar({
        papel: 'assistente',
        texto: r.resposta,
        status: r.status,
        sql: r.sql_executado,
        fontes: r.fontes,
        visualizacao: r.visualizacao,
      })
    } catch (e) {
      if (!montado.current) return
      adicionar({ papel: 'assistente', texto: mensagemDeErro(e), status: 'erro' })
    } finally {
      if (montado.current) setCarregando(false)
    }
  }

  function enviar(evento: FormEvent) {
    evento.preventDefault()
    void perguntar(texto)
  }

  function aoDigitar(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === 'Enter' && !evento.shiftKey) {
      evento.preventDefault()
      void perguntar(texto)
    }
  }

  function novaConversa() {
    const antiga = sessao.current
    sessao.current = novaSessao()
    setMensagens([])
    setTexto('')
    // Apagar o histórico no servidor é "melhor esforço": a conversa nova já começa limpa de qualquer forma.
    api.ia.limparSessao(antiga).catch(() => undefined)
  }

  return (
    <>
      <PageHeader
        eyebrow="INTELIGÊNCIA"
        title="Assistente IA"
        description="Pergunte em português sobre consumo, faturamento, interrupções e atendimento."
      />
      <Panel
        title="Converse com os dados"
        description="O assistente só consulta os dados, nunca altera nada. Se não souber, ele diz que não sabe."
        actions={
          <button type="button" className="button button--secondary button--small" onClick={novaConversa} disabled={mensagens.length === 0 && !carregando}>
            <RotateCcw size={14} aria-hidden="true" /> Nova conversa
          </button>
        }
        className="chat"
      >
        <div className="chat-log" role="log" aria-live="polite" aria-label="Conversa com o assistente">
          {mensagens.length === 0 && (
            <p className="muted">
              <Sparkles size={14} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6 }} />
              Comece por uma das perguntas abaixo ou escreva a sua.
            </p>
          )}
          {mensagens.map((m) => (
            <article key={m.id} className={`msg msg--${m.papel}${m.status ? ` msg--${m.status}` : ''}`}>
              {m.papel === 'assistente' && m.status && <span className="msg-label">{ROTULO[m.status]}</span>}
              <div className="msg-bubble">{m.texto}</div>
              {m.visualizacao && <VisualizacaoChart spec={m.visualizacao} />}
              {m.papel === 'assistente' && (m.sql || (m.fontes && m.fontes.length > 0)) && (
                <details>
                  <summary>Como cheguei a esta resposta</summary>
                  {m.fontes && m.fontes.length > 0 && (
                    <p>
                      <strong>Tabelas consultadas:</strong> {m.fontes.join(', ')}
                    </p>
                  )}
                  {m.sql && <pre><code>{m.sql}</code></pre>}
                </details>
              )}
            </article>
          ))}
          {carregando && (
            <article className="msg" aria-busy="true">
              <span className="msg-label">Consultando os dados… isso pode levar alguns segundos</span>
              <div className="msg-bubble">
                <span className="spinner" aria-hidden="true" />
              </div>
            </article>
          )}
          <div ref={fim} />
        </div>

        {mensagens.length === 0 && (
          <div className="suggestions" aria-label="Sugestões de perguntas">
            {SUGESTOES.map((s) => (
              <button key={s} type="button" onClick={() => void perguntar(s)} disabled={carregando}>
                {s}
              </button>
            ))}
          </div>
        )}

        <form className="chat-composer" onSubmit={enviar}>
          <label className="sr-only" htmlFor="pergunta-ia">
            Sua pergunta
          </label>
          <textarea
            id="pergunta-ia"
            rows={1}
            value={texto}
            maxLength={MAX}
            placeholder="Ex.: qual município teve mais interrupções este ano?"
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={aoDigitar}
          />
          <button type="submit" className="button button--primary" disabled={!valido || carregando}>
            <Send size={16} aria-hidden="true" /> Perguntar
          </button>
        </form>
        <p className="chat-meta">
          <span>Enter envia · Shift+Enter quebra a linha</span>
          <span>
            {tamanho}/{MAX}
          </span>
        </p>
      </Panel>
    </>
  )
}
