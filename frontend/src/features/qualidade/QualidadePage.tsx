import { useReducer, useState } from 'react'
import { RotateCcw, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api, useApi } from '../../api'
import { SelectField } from '../../components/ui/Controls'
import { DataCorte } from '../../components/ui/DataCorte'
import { ErrorState, LoadingState } from '../../components/ui/Feedback'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import {
  limitesDashboard as limites, periodoInicialDashboard as periodoPadrao, quantidadeMeses,
  referenciaInicialDashboard as referenciaPadrao, sugerirReferencia, validarPeriodo, validarPeriodosDashboard,
} from '../../utils/periodosDashboard'
import { parametrosDashboard } from '../dashboard/consultas'
import { alterarPeriodos, estadoInicial } from '../dashboard/periodos'
import { SeletorPeriodo } from '../dashboard/SeletorPeriodo'
import { CausasQualidade } from './CausasQualidade'
import { EvolucaoQualidade } from './EvolucaoQualidade'
import { quantidade } from './formatacao'
import { KpisQualidade } from './KpisQualidade'
import { RankingAlimentadores } from './RankingAlimentadores'
import '../dashboard/dashboard.css'
import './qualidade.css'

export function QualidadePage() {
  const [busca] = useSearchParams()
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites, referenciaPadrao),
    undefined, () => estadoInicial(periodoPadrao, referenciaPadrao),
  )
  const { periodo, comparar, referencia: comparacao, aviso } = temporal
  const referencia = comparar ? comparacao : null
  const quantidadePeriodo = quantidadeMeses(periodo)
  const [municipio, setMunicipio] = useState<string | null>(null)
  // Vindo da Visão 360 (?alimentador=), abre no alimentador da UC.
  const [alimentador, setAlimentador] = useState<string | null>(busca.get('alimentador')?.toUpperCase() || null)

  const deps = [periodo.inicio, periodo.fim, referencia?.inicio, referencia?.fim, municipio, alimentador]
  const resumo = useApi((signal) => api.continuidade.resumo({
    ...parametrosDashboard(periodo, referencia), municipio: municipio ?? undefined, alimentador: alimentador ?? undefined,
  }, signal), deps, { manterDadosAnteriores: true })
  const ranking = useApi((signal) => api.continuidade.alimentadores({ inicio: periodo.inicio, fim: periodo.fim, municipio: municipio ?? undefined }, signal),
    [periodo.inicio, periodo.fim, municipio], { manterDadosAnteriores: true })
  const rankingBase = useApi(async (signal) => referencia
    ? api.continuidade.alimentadores({ inicio: referencia.inicio, fim: referencia.fim, municipio: municipio ?? undefined }, signal) : null,
  [referencia?.inicio, referencia?.fim, municipio], { manterDadosAnteriores: true })
  const catalogo = useApi((signal) => api.filtros(signal), [])

  const opcoesAlimentador = [...(ranking.data ?? [])].sort((a, b) => a.alimentador_id.localeCompare(b.alimentador_id))
    .map((a) => ({ value: a.alimentador_id, label: municipio ? a.alimentador_id : `${a.alimentador_id} · ${a.municipio}` }))
  const dados = resumo.data
  const selecionado = ranking.data?.find((a) => a.alimentador_id === dados?.alimentador_id)
  const escopo = dados?.alimentador_id ?? dados?.municipio ?? 'Distribuidora'

  function escolherMunicipio(valor: string | null) {
    setMunicipio(valor)
    const atual = ranking.data?.find((a) => a.alimentador_id === alimentador)
    if (valor && atual && atual.municipio !== valor) setAlimentador(null)
  }

  function limpar() {
    dispatch({ tipo: 'limpar' })
    setMunicipio(null)
    setAlimentador(null)
  }

  return (
    <div className="qualidade-page">
      <PageHeader
        title="Qualidade do Serviço"
        description="DEC e FEC por alimentador: onde as interrupções se concentram e onde priorizar a manutenção."
      />

      <form className="panel qualidade-filtros" aria-label="Filtros da qualidade do serviço"
        onSubmit={(event) => event.preventDefault()} onReset={limpar}>
        <SeletorPeriodo key={`atual-${comparar}`} label="Período analisado" valor={periodo}
          minimo={limites.minimo} maximo={limites.maximo}
          validar={(valor) => validarPeriodo(valor, comparar ? 12 : 24, limites)}
          onChange={(valor) => dispatch({ tipo: 'periodo', valor })} />
        <div className="dashboard-reference">
          <SeletorPeriodo key={`base-${periodo.inicio}-${periodo.fim}`} label="Período de referência (opcional)" valor={comparacao}
            minimo={limites.minimo} maximo={limites.maximo} desabilitado={quantidadePeriodo > 12}
            sugestao={sugerirReferencia(periodo, limites)} mesesFixos={quantidadePeriodo}
            validar={(base) => validarPeriodosDashboard(periodo, base, true, limites)}
            onLimpar={() => dispatch({ tipo: 'comparar', valor: false })}
            onChange={(valor) => dispatch({ tipo: 'referencia', valor })} />
        </div>
        <SelectField label="Município" value={municipio ?? ''} placeholder="Todos os municípios"
          options={catalogo.data?.municipios.map((m) => ({ value: m.nome, label: m.nome })) ?? []}
          onChange={(valor) => escolherMunicipio(valor || null)} />
        <SelectField label="Alimentador" value={alimentador ?? ''} placeholder="Todos os alimentadores"
          options={opcoesAlimentador} onChange={(valor) => setAlimentador(valor || null)} />
        <button type="reset" className="button button--secondary"><RotateCcw size={14} aria-hidden="true" /> Limpar</button>
        <DataCorte />
        {aviso && <p className="qualidade-filtros-nota" role="status" aria-live="polite">{aviso}</p>}
        {catalogo.error && <p className="qualidade-filtros-nota" role="alert">
          Não foi possível carregar os municípios.{' '}
          <button type="button" className="link-button" onClick={catalogo.reload}>Tentar novamente</button>
        </p>}
      </form>

      {resumo.error ? <Panel title="Qualidade do serviço"><ErrorState error={resumo.error} onRetry={resumo.reload} /></Panel>
        : !dados ? <Panel title="Qualidade do serviço"><LoadingState label="Calculando os indicadores…" /></Panel>
          : <div className="qualidade-resultados" aria-busy={resumo.loading}>
            {resumo.loading && <div className="qualidade-atualizando"><LoadingState label="Atualizando indicadores…" /></div>}
            <div className="qualidade-resultados-conteudo" inert={resumo.loading}>
              <p className="qualidade-escopo">
                <span>Recorte: <strong>{escopo}</strong></span>
                {dados.alimentador_id
                  ? <>
                    {selecionado && <span>{selecionado.municipio}</span>}
                    {dados.atual?.qtd_ucs != null && <span>{quantidade(dados.atual.qtd_ucs)} UCs</span>}
                    <button type="button" className="badge qualidade-escopo-limpar" onClick={() => setAlimentador(null)}
                      aria-label="Remover filtro de alimentador">Ver {municipio ?? 'distribuidora'} <X size={12} aria-hidden="true" /></button>
                  </>
                  : <span>{quantidade(dados.qtd_alimentadores)} alimentadores{dados.atual?.qtd_ucs != null && ` · ${quantidade(dados.atual.qtd_ucs)} UCs`}</span>}
              </p>

              <KpisQualidade atual={dados.atual} base={dados.base} referencia={referencia} />

              <section className="qualidade-detalhe" aria-label="Evolução e causas">
                <EvolucaoQualidade serie={dados.serie} serieBase={dados.serie_base} periodo={periodo} referencia={referencia} escopo={escopo} />
                <CausasQualidade causas={dados.causas} />
              </section>

              {ranking.error ? <Panel title="Ranking dos alimentadores"><ErrorState error={ranking.error} onRetry={ranking.reload} /></Panel>
                : !ranking.data ? <Panel title="Ranking dos alimentadores"><LoadingState label="Carregando alimentadores…" /></Panel>
                  : <RankingAlimentadores alimentadores={ranking.data} base={rankingBase.data ?? null} referencia={referencia}
                    selecionado={alimentador} onSelecionar={(id) => {
                      setAlimentador(id === alimentador ? null : id)
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }} />}
            </div>
          </div>}
    </div>
  )
}
