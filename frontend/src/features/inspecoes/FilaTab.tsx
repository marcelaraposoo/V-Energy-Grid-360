import { useState } from 'react'
import type { FormEvent } from 'react'
import { ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Download, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, useApi } from '../../api'
import type { SuspeitaFila } from '../../api'
import { SelectField } from '../../components/ui/Controls'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { InsightsPanel } from '../../components/ui/InsightsPanel'
import { Panel } from '../../components/ui/Panel'
import { fmtDecimal, fmtInteiro, mensagemDeErro } from '../../utils/format'
import { urlExportarFila } from './api'
import '../../components/ui/portal.css'

const TAMANHO = 20
const PROBABILIDADES = [
  { value: '0.5', label: '50% ou mais' },
  { value: '0.7', label: '70% ou mais' },
  { value: '0.9', label: '90% ou mais' },
]

type Props = { onOrdemCriada: () => void }

export function FilaTab({ onOrdemCriada }: Props) {
  const [busca, setBusca] = useState('')
  const [termo, setTermo] = useState('')
  const [municipio, setMunicipio] = useState('')
  const [classe, setClasse] = useState('')
  const [prob, setProb] = useState('')
  const [pagina, setPagina] = useState(1)
  const [criando, setCriando] = useState<string | null>(null)
  const [aviso, setAviso] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null)

  const catalogo = useApi((signal) => api.filtros(signal), [])
  const fila = useApi(
    (signal) =>
      api.perdas.fila(
        { q: termo, municipio, classe, prob_minima: prob ? Number(prob) : undefined, pagina, tamanho: TAMANHO },
        signal,
      ),
    [termo, municipio, classe, prob, pagina],
  )

  const total = fila.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / TAMANHO))

  function filtrar<T>(definir: (v: T) => void) {
    return (valor: T) => {
      definir(valor)
      setPagina(1)
    }
  }

  function buscar(evento: FormEvent) {
    evento.preventDefault()
    setTermo(busca.trim())
    setPagina(1)
  }

  async function gerarOrdem(item: SuspeitaFila) {
    setCriando(item.uc_id)
    setAviso(null)
    try {
      const ordem = await api.perdas.criarOrdem({ uc_id: item.uc_id, motivo: item.motivos.join('; ') })
      setAviso({ tipo: 'success', texto: `Ordem #${ordem.id} criada para ${item.uc_id}. Ela saiu da fila e está em "Ordens".` })
      onOrdemCriada()
      fila.reload()
    } catch (e) {
      setAviso({ tipo: 'error', texto: mensagemDeErro(e) })
    } finally {
      setCriando(null)
    }
  }

  const exportar = urlExportarFila({
    q: termo,
    municipio,
    classe,
    prob_minima: prob ? Number(prob) : undefined,
    limite: 500,
  })

  return (
    <div className="stack">
      {aviso && (
        <p className={`notice notice--${aviso.tipo}`} role={aviso.tipo === 'error' ? 'alert' : 'status'}>
          {aviso.tipo === 'success' ? <CircleCheck size={16} aria-hidden="true" /> : <CircleAlert size={16} aria-hidden="true" />}
          <span>{aviso.texto}</span>
        </p>
      )}
      <Panel
        className="panel--filters"
        title="Unidades suspeitas"
        description="Da mais promissora para a menos promissora: prioridade = probabilidade × energia recuperável."
        actions={
          <a className="button button--secondary" href={exportar} download>
            <Download size={16} aria-hidden="true" /> Exportar CSV
          </a>
        }
      >
        <form className="filters" onSubmit={buscar} role="search">
          <label className="field" style={{ flex: '1 1 220px' }}>
            <span>Buscar por UC ou titular</span>
            <input value={busca} onChange={(e) => setBusca(e.target.value)} maxLength={100} placeholder="UC100000 ou nome" />
          </label>
          <button type="submit" className="button button--secondary">
            <Search size={16} aria-hidden="true" /> Buscar
          </button>
          <SelectField
            label="Município"
            value={municipio}
            onChange={filtrar(setMunicipio)}
            options={(catalogo.data?.municipios ?? []).map((m) => ({ value: m.nome, label: m.nome }))}
          />
          <SelectField
            label="Classe"
            value={classe}
            onChange={filtrar(setClasse)}
            options={(catalogo.data?.classes ?? []).map((c) => ({ value: c.codigo, label: `${c.codigo} · ${c.descricao}` }))}
          />
          <SelectField label="Probabilidade" value={prob} onChange={filtrar(setProb)} options={PROBABILIDADES} />
        </form>

        {fila.loading && !fila.data && <LoadingState label="Carregando a fila…" />}
        {fila.error && <ErrorState error={fila.error} onRetry={fila.reload} />}
        {fila.data && fila.data.itens.length === 0 && (
          <p className="feedback">Nenhuma unidade suspeita para este filtro.</p>
        )}
        {fila.data && fila.data.itens.length > 0 && (
          <div className="table-wrap" aria-busy={fila.loading}>
            <table className="data-table">
              <caption className="sr-only">Fila de unidades suspeitas, ordenada por prioridade</caption>
              <thead>
                <tr>
                  <th scope="col" className="num">#</th>
                  <th scope="col">UC</th>
                  <th scope="col">Local</th>
                  <th scope="col">Motivo da suspeita</th>
                  <th scope="col" className="num">Prob.</th>
                  <th scope="col" className="num">Energia a recuperar</th>
                  <th scope="col" className="num">Prioridade</th>
                  <th scope="col">
                    <span className="sr-only">Ação</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {fila.data.itens.map((s) => (
                  <tr key={s.uc_id}>
                    <td className="num">{s.posicao}</td>
                    <th scope="row">
                      <Link className="text-link" to={`/uc/${s.uc_id}`}>{s.uc_id}</Link>
                      <div className="muted">{s.titular}</div>
                    </th>
                    <td>
                      {s.municipio}
                      <div className="muted">{s.bairro} · {s.classe}</div>
                    </td>
                    <td className="wrap">
                      <div className="tag-list">
                        {s.motivos.map((m) => (
                          <span key={m} className="tag">{m}</span>
                        ))}
                      </div>
                    </td>
                    <td className="num">{fmtInteiro(s.probabilidade * 100)}%</td>
                    <td className="num">{fmtDecimal(s.energia_recuperavel_kwh_mes)} kWh/mês</td>
                    <td className="num">{fmtDecimal(s.prioridade_score)}</td>
                    <td>
                      <button
                        type="button"
                        className="button button--primary button--small"
                        disabled={criando !== null}
                        onClick={() => gerarOrdem(s)}
                      >
                        {criando === s.uc_id ? 'Criando…' : 'Gerar ordem'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {fila.data && total > 0 && (
          <div className="table-footer">
            <span>
              {fmtInteiro(total)} unidades na fila · página {pagina} de {paginas}
            </span>
            <span className="pager">
              <button type="button" className="button button--secondary button--small" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
                <ChevronLeft size={14} aria-hidden="true" /> Anterior
              </button>
              <button type="button" className="button button--secondary button--small" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>
                Próxima <ChevronRight size={14} aria-hidden="true" />
              </button>
            </span>
          </div>
        )}
      </Panel>
      <InsightsPanel
        tela="perdas"
        titulo="Insights da IA"
        descricao="Leitura automática da fila de inspeção"
        deps={[total]}
      />
    </div>
  )
}
