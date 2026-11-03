import { useReducer } from 'react'
import { ArrowRight, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, useApi } from '../../api'
import { DataCorte } from '../../components/ui/DataCorte'
import { PageHeader } from '../../components/ui/PageHeader'
import { linkReceita } from '../receita/periodos'
import { SeletorPeriodo } from './SeletorPeriodo'
import { InadimplenciaCard } from './InadimplenciaCard'
import { ClassesChart } from './ClassesChart'
import { EvolucaoPanel } from './EvolucaoPanel'
import { KpisPrincipais } from './KpisPrincipais'
import { UcsGdCard } from './UcsGdCard'
import { parametrosDashboard } from './consultas'
import { alterarPeriodos, estadoInicial } from './periodos'
import { limitesDashboard, periodoInicialDashboard, quantidadeMeses, referenciaInicialDashboard, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard'
import './dashboard.css'

const periodoPadrao = periodoInicialDashboard
const referenciaPadrao = referenciaInicialDashboard
const limites = limitesDashboard

export function DashboardPage() {
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites, referenciaPadrao),
    undefined, () => estadoInicial(periodoPadrao, referenciaPadrao),
  )
  const { periodo, comparar, referencia: comparacao, aviso } = temporal
  const referencia = comparar ? comparacao : null
  const params = parametrosDashboard(periodo, referencia)
  const deps = [periodo.inicio, periodo.fim, referencia?.inicio, referencia?.fim]
  const indicadores = useApi((signal) => api.dashboard.kpis({ ...params, indicador: 'executivo' }, signal), deps)
  const serie = useApi((signal) => api.dashboard.serie(params, signal), deps)
  const cadastro = useApi((signal) => api.dashboard.cadastroGd(params, signal), deps)
  const classes = useApi((signal) => api.dashboard.consumoClasses(params, signal), deps)
  const quantidade = quantidadeMeses(periodo)
  const validarReferencia = (base: typeof periodo) => validarPeriodosDashboard(periodo, base, true, limites)

  return (
    <div className="dashboard-page">
      <PageHeader
        title="Dashboard Executivo"
        description="Receita, consumo e indicadores do negócio em um só lugar."
        actions={<Link className="button button--secondary" to={linkReceita(periodo, referencia)}>
          Investigar na Análise de Receita <ArrowRight size={14} aria-hidden="true" />
        </Link>}
      />

      <form
        className="panel dashboard-filters"
        aria-label="Filtros do dashboard"
        onSubmit={(event) => event.preventDefault()}
        onReset={() => dispatch({ tipo: 'limpar' })}
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
        <button type="reset" className="button button--secondary">
          <RotateCcw size={14} aria-hidden="true" /> Limpar
        </button>
        <DataCorte />
        {aviso && <p className="dashboard-temporal-help" role="status" aria-live="polite">{aviso}</p>}
      </form>

      <KpisPrincipais estado={indicadores} referencia={referencia} />

      <section className="dashboard-complementary" aria-label="Indicadores complementares e consumo por classe">
        <div className="dashboard-complementary-stack">
          <InadimplenciaCard periodo={periodo} referencia={referencia} estado={indicadores} />
          <UcsGdCard competencia={periodo.fim} referencia={referencia} estado={cadastro} />
        </div>
        <ClassesChart key={`${periodo.inicio}-${periodo.fim}-${referencia?.inicio}-${referencia?.fim}`}
          periodo={periodo} referencia={referencia} estado={classes} />
      </section>

      <section className="dashboard-charts" aria-label="Evolução mensal">
        <EvolucaoPanel estado={serie} periodo={periodo} referencia={referencia} campo="receita" />
        <EvolucaoPanel estado={serie} periodo={periodo} referencia={referencia} campo="energia_kwh" />
      </section>
    </div>
  )
}
