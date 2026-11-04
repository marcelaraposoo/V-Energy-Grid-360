import { useReducer, useState } from 'react'
import { ArrowRight, RotateCcw } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, useApi } from '../../api'
import { SelectField } from '../../components/ui/Controls'
import { DataCorte } from '../../components/ui/DataCorte'
import { PageHeader } from '../../components/ui/PageHeader'
import { linkQualidade } from '../qualidade/url'
import { linkReceita } from '../receita/periodos'
import { SeletorPeriodo } from './SeletorPeriodo'
import { InadimplenciaCard } from './InadimplenciaCard'
import { ClassesChart, type AgrupamentoConsumo } from './ClassesChart'
import { EvolucaoPanel } from './EvolucaoPanel'
import { KpisPrincipais } from './KpisPrincipais'
import { OperacaoCards } from './OperacaoCards'
import { UcsGdCard } from './UcsGdCard'
import { parametrosDashboard } from './consultas'
import { alterarPeriodos, estadoInicial } from './periodos'
import { limitesDashboard, periodoInicialDashboard, quantidadeMeses, referenciaInicialDashboard, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard'
import './dashboard.css'

const periodoPadrao = periodoInicialDashboard
const referenciaPadrao = referenciaInicialDashboard
const limites = limitesDashboard

export function DashboardPage() {
  const [busca] = useSearchParams()
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites, referenciaPadrao),
    undefined, () => estadoInicial(periodoPadrao, referenciaPadrao),
  )
  const { periodo, comparar, referencia: comparacao, aviso } = temporal
  const referencia = comparar ? comparacao : null
  // Só município: todos os blocos (inclusive DEC/FEC, que a A8 tem por município) seguem disponíveis.
  const [municipio, setMunicipio] = useState<string | null>(() => busca.get('municipio') || null)
  const params = { ...parametrosDashboard(periodo, referencia), ...(municipio ? { municipio } : {}) }
  const deps = [periodo.inicio, periodo.fim, referencia?.inicio, referencia?.fim, municipio]
  const catalogo = useApi((signal) => api.filtros(signal), [])
  const indicadores = useApi((signal) => api.dashboard.kpis({ ...params, indicador: 'executivo' }, signal), deps)
  const serie = useApi((signal) => api.dashboard.serie(params, signal), deps)
  const cadastro = useApi((signal) => api.dashboard.cadastroGd(params, signal), deps)
  const classes = useApi((signal) => api.dashboard.consumoClasses(params, signal), deps)
  const operacao = useApi((signal) => api.dashboard.operacao(params, signal), deps)
  // Consumo por local só é buscado quando a visão está aberta.
  const [agrupamento, setAgrupamento] = useState<AgrupamentoConsumo>('classe')
  const locais = useApi((signal) => agrupamento === 'local' ? api.dashboard.consumoLocais(params, signal) : Promise.resolve(null),
    [...deps, agrupamento])
  const quantidade = quantidadeMeses(periodo)
  const validarReferencia = (base: typeof periodo) => validarPeriodosDashboard(periodo, base, true, limites)

  return (
    <div className="dashboard-page">
      <PageHeader
        title="Dashboard Executivo"
        description="Receita, consumo e indicadores do negócio em um só lugar."
        actions={<Link className="link-button dashboard-investigar" to={linkReceita(periodo, referencia, municipio)}>
          Investigar na Análise de Receita <ArrowRight size={14} aria-hidden="true" />
        </Link>}
      />

      <form
        className="panel dashboard-filters"
        aria-label="Filtros do dashboard"
        onSubmit={(event) => event.preventDefault()}
        onReset={() => {
          dispatch({ tipo: 'limpar' })
          setMunicipio(null)
        }}
      >
        <SeletorPeriodo
          key={`atual-${comparar}`}
          label="Período analisado"
          valor={periodo}
          minimo={limites.minimo}
          maximo={limites.maximo}
          validar={(valor) => validarPeriodo(valor, comparar ? 12 : 24, limites)}
          onChange={(valor) => dispatch({ tipo: 'periodo', valor })}
        />
        <div className="dashboard-reference">
          <SeletorPeriodo
            key={`base-${periodo.inicio}-${periodo.fim}`}
            label="Período de referência (opcional)"
            valor={comparacao}
            minimo={limites.minimo}
            maximo={limites.maximo}
            desabilitado={quantidade > 12}
            sugestao={sugerirReferencia(periodo, limites)}
            mesesFixos={quantidade}
            validar={validarReferencia}
            onLimpar={() => dispatch({ tipo: 'comparar', valor: false })}
            onChange={(valor) => dispatch({ tipo: 'referencia', valor })}
          />
        </div>
        <SelectField label="Município" value={municipio ?? ''} placeholder="Todos os municípios"
          options={catalogo.data?.municipios.map((m) => ({ value: m.nome, label: m.nome })) ?? []}
          onChange={(valor) => setMunicipio(valor || null)} />
        <button type="reset" className="button button--secondary">
          <RotateCcw size={14} aria-hidden="true" /> Limpar
        </button>
        <DataCorte />
        {aviso && <p className="dashboard-temporal-help" role="status" aria-live="polite">{aviso}</p>}
      </form>

      {/* Ordem: resultado do período, como chegou nele (evolução), o detalhe comercial e a operação. */}
      <KpisPrincipais estado={indicadores} referencia={referencia} />

      <section className="dashboard-charts" aria-label="Evolução mensal">
        <EvolucaoPanel estado={serie} periodo={periodo} referencia={referencia} campo="receita" />
        <EvolucaoPanel estado={serie} periodo={periodo} referencia={referencia} campo="energia_kwh" />
      </section>

      {/* Embaixo de cada gráfico, o que o detalha: faturamento em aberto e base sob a receita; classes sob a energia. */}
      <section className="dashboard-complementary" aria-label="Indicadores complementares e consumo por classe">
        <div className="dashboard-complementary-stack">
          <InadimplenciaCard periodo={periodo} referencia={referencia} estado={indicadores} />
          <UcsGdCard competencia={periodo.fim} referencia={referencia} estado={cadastro} />
        </div>
        <ClassesChart key={`${periodo.inicio}-${periodo.fim}-${referencia?.inicio}-${referencia?.fim}-${municipio}`}
          periodo={periodo} referencia={referencia} estado={classes}
          agrupamento={agrupamento} onAgrupamento={setAgrupamento} locais={locais} municipio={municipio} onMunicipio={setMunicipio} />
      </section>

      <OperacaoCards estado={operacao} referencia={referencia} municipio={municipio}
        linkQualidade={linkQualidade(periodo, referencia, municipio)} />
    </div>
  )
}
