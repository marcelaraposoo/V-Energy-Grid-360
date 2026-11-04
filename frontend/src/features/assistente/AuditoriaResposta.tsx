import type { AuditoriaIa } from '../../api/types'

type Props = {
  auditoria: AuditoriaIa
  sql?: string | null
  fontes?: string[]
}

const ROTULO_ETAPA: Record<AuditoriaIa['etapas'][number]['status'], string> = {
  completed: 'Concluída',
  blocked: 'Bloqueada',
  skipped: 'Não executada',
  error: 'Erro',
  cache_hit: 'Cache',
}

const ROTULO_RESULTADO: Record<string, string> = {
  answered: 'Respondida',
  no_data: 'Sem dados',
  needs_clarification: 'Precisa de esclarecimento',
  out_of_scope: 'Fora do escopo',
  insufficient_context: 'Contexto insuficiente',
  request_rejected: 'Solicitação rejeitada',
  input_blocked: 'Entrada bloqueada',
  sql_blocked: 'SQL bloqueado',
  output_blocked: 'Resposta bloqueada',
  provider_error: 'Falha no provedor',
  execution_error: 'Falha na execução',
  internal_error: 'Falha interna',
}

const ROTULO_ETAPA_FINAL: Record<string, string> = {
  input_guardrail: 'C1 · Entrada',
  sql_generation: 'C4.1 · Geração SQL',
  sql_guardrail: 'C4.2 · Segurança SQL',
  sql_execution: 'C4.3 · Execução SQL',
  synthesis: 'C4.4 · Síntese',
  output_guardrail: 'C5 · Saída',
  post_processing: 'C6 · Pós-processamento',
  done: 'C7 · Finalização',
}

function formatarDuracao(valor: number | null | undefined): string {
  if (valor == null || !Number.isFinite(valor)) return '—'
  if (valor < 1000) return `${Math.round(valor)} ms`
  return `${(valor / 1000).toFixed(2)} s`
}

function formatarFase(fase: string | null): string {
  if (fase === 'sql_generation') return 'Geração SQL'
  if (fase === 'synthesis') return 'Síntese'
  return 'Fase não informada'
}

function formatarPersistencia(status: AuditoriaIa['persistencia']): string {
  if (status === 'salva') return 'Registro salvo em portal.db'
  if (status === 'falha') return 'Falha ao salvar o registro'
  return 'Armazenamento de auditoria indisponível'
}

export function AuditoriaResposta({ auditoria, sql, fontes = [] }: Props) {
  return (
    <details className="audit-details">
      <summary>
        <span>Auditoria desta resposta</span>
        <code>{auditoria.request_id ? auditoria.request_id.slice(0, 8) : 'sem ID'}</code>
      </summary>
      <div className="audit-content">
        <div className="audit-summary-grid">
          <div className="audit-metric">
            <span>Resultado</span>
            <strong>{ROTULO_RESULTADO[auditoria.resultado] ?? auditoria.resultado}</strong>
          </div>
          <div className="audit-metric">
            <span>Etapa final</span>
            <strong>{ROTULO_ETAPA_FINAL[auditoria.etapa_final] ?? auditoria.etapa_final}</strong>
          </div>
          <div className="audit-metric">
            <span>Duração do processamento</span>
            <strong>{formatarDuracao(auditoria.duracao_ms)}</strong>
          </div>
          <div className="audit-metric">
            <span>Linhas retornadas</span>
            <strong>{auditoria.linhas_retornadas ?? '—'}</strong>
          </div>
        </div>

        <div className="audit-flags">
          <span className={auditoria.cache_hit ? 'audit-flag audit-flag--active' : 'audit-flag'}>
            {auditoria.cache_hit ? 'Resposta recuperada do cache' : 'Cache não utilizado'}
          </span>
          <span className="audit-flag">Regenerações: {auditoria.regeneracoes}</span>
          {auditoria.resultado_truncado === true && (
            <span className="audit-flag audit-flag--warning">Resultado limitado por truncamento</span>
          )}
          <span className={`audit-flag audit-flag--${auditoria.persistencia}`}>
            {formatarPersistencia(auditoria.persistencia)}
          </span>
        </div>

        <section className="audit-section" aria-label="Etapas do pipeline">
          <h4>Rastro do pipeline</h4>
          <ol className="audit-steps">
            {auditoria.etapas.map((etapa) => (
              <li className={`audit-step audit-step--${etapa.status}`} key={etapa.codigo}>
                <div className="audit-step-heading">
                  <strong>{etapa.codigo} · {etapa.nome}</strong>
                  <span>{ROTULO_ETAPA[etapa.status]}</span>
                </div>
                {etapa.detalhe && <p>{etapa.detalhe}</p>}
                {etapa.duracao_ms != null && (
                  <small>{formatarDuracao(etapa.duracao_ms)}</small>
                )}
              </li>
            ))}
          </ol>
        </section>

        {auditoria.tentativas_provedor.length > 0 && (
          <section className="audit-section" aria-label="Tentativas dos provedores">
            <h4>Tentativas dos provedores</h4>
            <div className="audit-attempts">
              {auditoria.tentativas_provedor.map((tentativa, index) => (
                <div className="audit-attempt" key={`${tentativa.provedor}-${tentativa.fase}-${tentativa.tentativa}-${index}`}>
                  <div>
                    <strong>{tentativa.provedor}</strong>
                    <span>{formatarFase(tentativa.fase)} · tentativa {tentativa.tentativa}</span>
                  </div>
                  <div className="audit-attempt-result">
                    <span className={tentativa.sucesso ? 'audit-success' : 'audit-error'}>
                      {tentativa.sucesso ? 'Sucesso' : `Falha${tentativa.tipo_erro ? ` · ${tentativa.tipo_erro}` : ''}`}
                    </span>
                    <small>{formatarDuracao(tentativa.latencia_ms)}</small>
                  </div>
                  <small className="audit-model">{tentativa.modelo}</small>
                </div>
              ))}
            </div>
          </section>
        )}

        {(fontes.length > 0 || sql) && (
          <section className="audit-section" aria-label="Consulta e fontes">
            <h4>Consulta e fontes</h4>
            {fontes.length > 0 && (
              <p><strong>Tabelas de origem:</strong> {fontes.join(', ')}</p>
            )}
            {sql && (
              <>
                <p><strong>SQL gerado e validado:</strong></p>
                {auditoria.cache_hit && (
                  <p className="muted">O resultado foi recuperado do cache pós-SQL; a consulta exibida foi validada, mas não foi executada novamente nesta requisição.</p>
                )}
                <pre><code>{sql}</code></pre>
              </>
            )}
          </section>
        )}

        <p className="audit-request-id">ID da requisição: <code>{auditoria.request_id || 'não informado'}</code></p>
      </div>
    </details>
  )
}
