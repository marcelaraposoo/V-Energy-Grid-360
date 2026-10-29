import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { CircleAlert, CircleCheck, Download, FileUp, Info } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, useApi } from '../../api'
import type { Ordem, StatusOrdem } from '../../api'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { Panel } from '../../components/ui/Panel'
import { fmtDataHora, fmtDecimal, mensagemDeErro } from '../../utils/format'
import { importarResultados, urlModeloResultados } from './api'
import type { ResumoImportacao } from './api'
import { ResultadoDialog } from './ResultadoDialog'
import { TIPOS } from './tipos'
import '../../components/ui/portal.css'

type Filtro = StatusOrdem | 'TODAS'

const ROTULO_STATUS: Record<StatusOrdem, string> = {
  PENDENTE: 'Pendente',
  EM_CAMPO: 'Em campo',
  CONCLUIDA: 'Concluída',
  CANCELADA: 'Cancelada',
}
const FILTROS: { valor: Filtro; rotulo: string }[] = [
  { valor: 'TODAS', rotulo: 'Todas' },
  { valor: 'PENDENTE', rotulo: 'Pendentes' },
  { valor: 'EM_CAMPO', rotulo: 'Em campo' },
  { valor: 'CONCLUIDA', rotulo: 'Concluídas' },
  { valor: 'CANCELADA', rotulo: 'Canceladas' },
]

const ativa = (o: Ordem) => o.status === 'PENDENTE' || o.status === 'EM_CAMPO'
const rotuloTipo = (tipo: string) => TIPOS.find((t) => t.valor === tipo)?.rotulo ?? tipo

type Props = { versao: number }

export function OrdensTab({ versao }: Props) {
  const [filtro, setFiltro] = useState<Filtro>('TODAS')
  const [emAcao, setEmAcao] = useState<number | null>(null)
  const [aviso, setAviso] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null)
  const [paraResultado, setParaResultado] = useState<Ordem | null>(null)
  const [importando, setImportando] = useState(false)
  const [resumo, setResumo] = useState<ResumoImportacao | null>(null)
  const entradaArquivo = useRef<HTMLInputElement>(null)

  const ordens = useApi((signal) => api.perdas.listarOrdens(undefined, signal), [versao])

  const todas = useMemo(() => [...(ordens.data ?? [])].sort((a, b) => b.id - a.id), [ordens.data])
  const visiveis = filtro === 'TODAS' ? todas : todas.filter((o) => o.status === filtro)
  const contagem = (f: Filtro) => (f === 'TODAS' ? todas.length : todas.filter((o) => o.status === f).length)
  const recuperada = todas.reduce((soma, o) => soma + (o.resultado?.energia_recuperada_kwh ?? 0), 0)

  async function executar(ordem: Ordem, acao: () => Promise<Ordem>, sucesso: string) {
    setEmAcao(ordem.id)
    setAviso(null)
    try {
      await acao()
      setAviso({ tipo: 'success', texto: sucesso })
      ordens.reload()
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensagemDeErro(e) })
    } finally {
      setEmAcao(null)
    }
  }

  function cancelar(ordem: Ordem) {
    if (!window.confirm(`Cancelar a ordem #${ordem.id} da unidade ${ordem.uc_id}? Essa ação não pode ser desfeita.`)) return
    void executar(ordem, () => api.perdas.cancelarOrdem(ordem.id), `Ordem #${ordem.id} cancelada.`)
  }

  async function enviarPlanilha(evento: ChangeEvent<HTMLInputElement>) {
    const arquivo = evento.target.files?.[0]
    evento.target.value = ''
    if (!arquivo) return
    setImportando(true)
    setResumo(null)
    setAviso(null)
    try {
      setResumo(await importarResultados(arquivo))
      ordens.reload()
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensagemDeErro(e) })
    } finally {
      setImportando(false)
    }
  }

  return (
    <div className="stack">
      {aviso && (
        <p className={`notice notice--${aviso.tipo}`} role={aviso.tipo === 'error' ? 'alert' : 'status'}>
          {aviso.tipo === 'success' ? <CircleCheck size={16} aria-hidden="true" /> : <CircleAlert size={16} aria-hidden="true" />}
          <span>{aviso.texto}</span>
        </p>
      )}

      <Panel
        className="ordens-panel"
        title="Ordens de inspeção"
        description="Acompanhe cada ordem da fila até o resultado de campo."
        actions={
          <div className="segmented" role="group" aria-label="Filtrar por status">
            {FILTROS.map((f) => (
              <button
                key={f.valor}
                type="button"
                className="button button--secondary"
                aria-pressed={filtro === f.valor}
                onClick={() => setFiltro(f.valor)}
              >
                {f.rotulo} ({contagem(f.valor)})
              </button>
            ))}
          </div>
        }
      >
        {ordens.loading && !ordens.data && <LoadingState label="Carregando ordens…" />}
        {ordens.error && <ErrorState error={ordens.error} onRetry={ordens.reload} />}
        {ordens.data && visiveis.length === 0 && (
          <p className="feedback">
            {todas.length === 0
              ? 'Nenhuma ordem ainda. Gere ordens a partir da fila de suspeitas.'
              : 'Nenhuma ordem com este status.'}
          </p>
        )}
        {visiveis.length > 0 && (
          <div className="table-wrap" aria-busy={ordens.loading}>
            <table className="data-table">
              <caption className="sr-only">Ordens de inspeção</caption>
              <thead>
                <tr>
                  <th scope="col" className="num">Ordem</th>
                  <th scope="col">UC</th>
                  <th scope="col">Status</th>
                  <th scope="col">Motivo</th>
                  <th scope="col">Criada em</th>
                  <th scope="col">Resultado de campo</th>
                  <th scope="col">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visiveis.map((o) => (
                  <tr key={o.id}>
                    <th scope="row" className="num">#{o.id}</th>
                    <td>
                      <Link className="text-link" to={`/uc/${o.uc_id}`}>{o.uc_id}</Link>
                    </td>
                    <td>
                      <span className={`status status--${o.status}`}>{ROTULO_STATUS[o.status]}</span>
                    </td>
                    <td className="wrap">{o.motivo ?? <span className="muted">—</span>}</td>
                    <td>{fmtDataHora(o.criada_em)}</td>
                    <td className="wrap">
                      {o.resultado ? (
                        <>
                          {rotuloTipo(o.resultado.tipo)}
                          <div className="muted">{fmtDecimal(o.resultado.energia_recuperada_kwh)} kWh recuperados</div>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {ativa(o) && (
                        <span className="row-actions">
                          {o.status === 'PENDENTE' && (
                            <button
                              type="button"
                              className="button button--secondary button--small"
                              disabled={emAcao !== null}
                              onClick={() =>
                                void executar(o, () => api.perdas.iniciarOrdem(o.id), `Ordem #${o.id} enviada a campo.`)
                              }
                            >
                              Enviar a campo
                            </button>
                          )}
                          <button
                            type="button"
                            className="button button--primary button--small"
                            disabled={emAcao !== null}
                            onClick={() => setParaResultado(o)}
                          >
                            Registrar resultado
                          </button>
                          <button
                            type="button"
                            className="button button--danger button--small"
                            disabled={emAcao !== null}
                            onClick={() => cancelar(o)}
                          >
                            Cancelar
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {todas.length > 0 && (
          <div className="table-footer">
            <span>Energia recuperada nas ordens concluídas</span>
            <strong>{fmtDecimal(recuperada)} kWh</strong>
          </div>
        )}
      </Panel>

      <Panel
        title="Resultados em lote"
        description="Baixe o modelo com as ordens em aberto, a equipe preenche em campo e você envia de volta."
      >
        <div className="filters">
          <a className="button button--secondary" href={urlModeloResultados()} download>
            <Download size={16} aria-hidden="true" /> Baixar modelo (CSV)
          </a>
          <button
            type="button"
            className="button button--primary"
            disabled={importando}
            onClick={() => entradaArquivo.current?.click()}
          >
            <FileUp size={16} aria-hidden="true" /> {importando ? 'Enviando…' : 'Enviar planilha preenchida'}
          </button>
          <input
            ref={entradaArquivo}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            tabIndex={-1}
            aria-label="Planilha de resultados em CSV"
            onChange={(e) => void enviarPlanilha(e)}
          />
        </div>
        <p className="insights-note">
          Preencha <code>tipo</code> ({TIPOS.map((t) => t.valor).join(', ')}), <code>energia_recuperada_kwh</code> e{' '}
          <code>observacoes</code>. Linhas com erro não são registradas e aparecem listadas abaixo.
        </p>
        {resumo && (
          <div style={{ padding: '0 22px 20px' }}>
            <div className={`notice ${resumo.rejeitadas.length ? '' : 'notice--success'}`} role="status">
              <Info size={16} aria-hidden="true" />
              <div>
                {resumo.aceitas} de {resumo.total} resultados registrados.
                {resumo.ignoradas > 0 && ` ${resumo.ignoradas} linhas sem preenchimento foram ignoradas.`}
                {resumo.rejeitadas.length > 0 && (
                  <ul>
                    {resumo.rejeitadas.map((r) => (
                      <li key={`${r.linha}-${r.erro}`}>
                        Linha {r.linha}
                        {r.ordem_id !== null ? ` (ordem #${r.ordem_id})` : ''}: {r.erro}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </Panel>

      <ResultadoDialog
        ordem={paraResultado}
        onFechar={() => setParaResultado(null)}
        onRegistrado={(o) => {
          setParaResultado(null)
          setAviso({ tipo: 'success', texto: `Resultado da ordem #${o.id} registrado.` })
          ordens.reload()
        }}
      />
    </div>
  )
}
