import { useReducer, useState } from 'react'
import {
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  CircleDollarSign,
  Headphones,
  RotateCcw,
  Sun,
  Users,
  Zap,
  ChartNoAxesCombined,
} from 'lucide-react'
import { api, useApi } from '../../api'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { EmptyState } from '../../components/ui/EmptyState'
import { EvolucaoChart } from './EvolucaoChart'
import { SeletorPeriodo } from './SeletorPeriodo'
import { SeletorFiltro } from './SeletorFiltro'
import { InadimplenciaCard } from './InadimplenciaCard'
import { parametrosInadimplencia } from './inadimplencia'
import { dashboardMock, dadosPeriodoMock, locaisMock } from './mockData'
import { alterarPeriodos, estadoInicial } from './periodos'
import { quantidadeMeses, sugerirReferencia, validarPeriodo, validarPeriodosDashboard } from '../../utils/periodosDashboard'
import './dashboard.css'

const numero = new Intl.NumberFormat('pt-BR')
const compacto = new Intl.NumberFormat('pt-BR', {
  notation: 'compact',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})
const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})
const percentual = new Intl.NumberFormat('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})
const total = (valores: number[]) =>
  valores.reduce((soma, valor) => soma + valor, 0)
const { atual, indicadores } = dashboardMock
const periodoPadrao = { inicio: atual.inicio, fim: atual.fim }
const limites = { minimo: dashboardMock.inicioBase, maximo: atual.fim }

export function DashboardPage() {
  const [municipio, setMunicipio] = useState('')
  const [bairro, setBairro] = useState('')
  const [classe, setClasse] = useState('')
  const [temporal, dispatch] = useReducer(
    (estado: ReturnType<typeof estadoInicial>, acao: Parameters<typeof alterarPeriodos>[1]) => alterarPeriodos(estado, acao, periodoPadrao, limites),
    undefined, () => estadoInicial(periodoPadrao),
  )
  const { periodo, comparar, referencia: comparacao, aviso } = temporal
  const inadimplencia = useApi(
    (signal) => api.dashboard.kpis(parametrosInadimplencia(periodo, comparar ? comparacao : null, { municipio, bairro, classe }), signal),
    [periodo.inicio, periodo.fim, comparar, comparacao?.inicio, comparacao?.fim, municipio, bairro, classe],
  )
  const dadosAtual = dadosPeriodoMock(periodo)
  const dadosReferencia = comparar && comparacao ? dadosPeriodoMock(comparacao) : null
  const receitaAtual = dadosAtual ? total(dadosAtual.receita) : null
  const receitaReferencia = dadosReferencia ? total(dadosReferencia.receita) : null
  const consumoAtual = dadosAtual ? total(dadosAtual.consumo) : null
  const consumoReferencia = dadosReferencia ? total(dadosReferencia.consumo) : null
  const ucsNoMes = (mes: string | undefined) => mes === '2026-06' ? indicadores.ucsFaturadas
    : mes === '2025-06' ? indicadores.ucsFaturadasReferencia : null
  const ucsAtual = ucsNoMes(periodo.fim)
  const ucsReferencia = comparar ? ucsNoMes(comparacao?.fim) : null
  const quantidade = quantidadeMeses(periodo)
  const validarReferencia = (base: typeof periodo) => validarPeriodosDashboard(periodo, base, true, limites)
  const bairros = locaisMock.find((local) => local.municipio === municipio)?.bairros ?? []
  const kpis = [
    {
      label: 'Receita faturada',
      icon: Banknote,
      valor: receitaAtual === null ? '—' : `R$ ${compacto.format(receitaAtual)}`,
      detalhe: 'Valor da energia, sem tributos',
      atual: receitaAtual,
      referencia: receitaReferencia,
    },
    {
      label: 'Consumo faturado',
      icon: Zap,
      valor: consumoAtual === null ? '—' : `${compacto.format(consumoAtual)} kWh`,
      detalhe: 'Energia faturada no período',
      atual: consumoAtual,
      referencia: consumoReferencia,
    },
    {
      label: 'UCs faturadas',
      icon: Users,
      valor: ucsAtual === null ? '—' : numero.format(ucsAtual),
      detalhe: `${periodo.fim} · unidades com fatura no mês`,
      atual: ucsAtual,
      referencia: ucsReferencia,
    },
    {
      label: 'Preço médio por kWh',
      icon: CircleDollarSign,
      valor: receitaAtual === null || !consumoAtual ? '—' : moeda.format(receitaAtual / consumoAtual),
      detalhe: 'Receita de energia / consumo faturado',
      atual: receitaAtual === null || !consumoAtual ? null : receitaAtual / consumoAtual,
      referencia: receitaReferencia === null || !consumoReferencia ? null : receitaReferencia / consumoReferencia,
    },
  ]

  return (
    <div className="dashboard-page">
      <PageHeader
        title="Dashboard Executivo"
        description="Receita, consumo e indicadores do negócio em um só lugar."
      />

      <form
        className="panel dashboard-filters"
        aria-label="Filtros do dashboard"
        onSubmit={(event) => event.preventDefault()}
        onReset={() => {
          setMunicipio('')
          setBairro('')
          setClasse('')
          dispatch({ tipo: 'limpar' })
        }}
      >
        <SeletorPeriodo
          key={`atual-${comparar}`}
          label="Período analisado"
          valor={periodo}
          minimo={dashboardMock.inicioBase}
          maximo={atual.fim}
          validar={(valor) => validarPeriodo(valor, comparar ? 12 : 24, limites)}
          onChange={(valor) => dispatch({ tipo: 'periodo', valor })}
        />
        <div className="dashboard-reference">
          <SeletorPeriodo
            key={`base-${periodo.inicio}-${periodo.fim}`}
            label="Período de referência (opcional)"
            valor={comparacao}
            minimo={dashboardMock.inicioBase}
            maximo={atual.fim}
            desabilitado={quantidade > 12}
            sugestao={sugerirReferencia(periodo, limites)}
            mesesFixos={quantidade}
            validar={validarReferencia}
            onLimpar={() => dispatch({ tipo: 'comparar', valor: false })}
            onChange={(valor) => dispatch({ tipo: 'referencia', valor })}
          />
        </div>
        <SeletorFiltro
          label="Município"
          valor={municipio}
          placeholder="Todos os municípios"
          opcoes={locaisMock.map((local) => local.municipio)}
          onChange={(selecionado) => {
            setMunicipio(selecionado)
            setBairro('')
          }}
        />
        <SeletorFiltro
          label="Bairro"
          valor={bairro}
          placeholder={
            municipio ? 'Todos os bairros' : 'Selecione um município'
          }
          opcoes={bairros}
          desabilitado={!municipio}
          onChange={setBairro}
        />
        <SeletorFiltro
          label="Classe de consumo"
          valor={classe}
          placeholder="Todas as classes"
          opcoes={[
            'Residencial',
            'Comercial',
            'Industrial',
            'Rural',
            'Poder público',
          ]}
          onChange={setClasse}
        />
        <button type="reset" className="button button--secondary">
          <RotateCcw size={14} aria-hidden="true" /> Limpar
        </button>
        {aviso && <p className="dashboard-temporal-help" role="status" aria-live="polite">{aviso}</p>}
      </form>

      <section className="dashboard-kpis" aria-label="Indicadores principais">
        {kpis.map(
          ({ label, icon: Icon, valor, detalhe, atual, referencia }) => {
            const variacao = comparar && atual !== null && referencia !== null && referencia !== 0
              ? (atual / referencia - 1) * 100 : null
            const Seta = variacao !== null && variacao < 0 ? ArrowDownRight : ArrowUpRight
            return (
              <article className="panel dashboard-kpi" key={label}>
                <h2>
                  <Icon size={17} strokeWidth={1.5} aria-hidden="true" />
                  {label}
                </h2>
                <p className="dashboard-kpi-value">{valor}</p>
                <p className="dashboard-kpi-detail">{detalhe}</p>
                {comparar && <p className="dashboard-kpi-comparison">
                  {variacao !== null ? <><span>
                    <Seta size={15} aria-hidden="true" />
                    {percentual.format(variacao)}%
                  </span>
                  vs. referência</> : 'Sem dados para comparação'}
                </p>}
              </article>
            )
          },
        )}
      </section>

      <div className="dashboard-charts">
        <Panel
          title="Evolução da receita"
          description={`Receita de energia, sem tributos · ${quantidade === 1 ? 'R$' : 'R$ milhões'}`}
        >
          {dadosAtual ? <EvolucaoChart
            key={`${periodo.inicio}-${periodo.fim}-${comparacao?.inicio}-${comparar}`}
            titulo="Receita mensal"
            unidade="R$"
            atual={dadosAtual.receita}
            referencia={dadosReferencia?.receita}
            periodoAtual={periodo}
            periodoReferencia={comparar ? comparacao : null}
          /> : <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período"
            description="Os dados fictícios de apresentação não cobrem todo o intervalo selecionado." compact />}
        </Panel>
        <Panel
          title="Evolução do consumo"
          description={`Energia faturada · ${quantidade === 1 ? 'kWh' : 'milhões de kWh'}`}
        >
          {dadosAtual ? <EvolucaoChart
            key={`${periodo.inicio}-${periodo.fim}-${comparacao?.inicio}-${comparar}`}
            titulo="Consumo mensal"
            unidade="kWh"
            atual={dadosAtual.consumo}
            referencia={dadosReferencia?.consumo}
            periodoAtual={periodo}
            periodoReferencia={comparar ? comparacao : null}
          /> : <EmptyState icon={ChartNoAxesCombined} title="Sem dados para o período"
            description="Os dados fictícios de apresentação não cobrem todo o intervalo selecionado." compact />}
        </Panel>
      </div>

      <section
        className="dashboard-secondary"
        aria-label="Indicadores complementares"
      >
        <InadimplenciaCard periodo={periodo} referencia={comparar ? comparacao : null} estado={inadimplencia} />
        <Panel
          title="Geração distribuída"
          description="Conectada até Jun/2026"
          actions={<Sun size={18} aria-hidden="true" />}
        >
          <div className="dashboard-secondary-body">
            <div className="dashboard-secondary-main">
              <p className="dashboard-secondary-value">
                {numero.format(indicadores.ucsGd)}
                <small>UCs</small>
              </p>
              <p>
                {(
                  (indicadores.ucsGd / indicadores.ucsCadastradas) *
                  100
                ).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}
                % da base cadastrada
              </p>
            </div>
            <div className="dashboard-secondary-detail">
              <span>UCs cadastradas</span>
              <strong>{numero.format(indicadores.ucsCadastradas)}</strong>
            </div>
          </div>
        </Panel>
        <Panel
          title="Atendimento"
          description="Chamados abertos de Jul/2025 a Jun/2026"
          actions={<Headphones size={18} aria-hidden="true" />}
        >
          <div className="dashboard-secondary-body">
            <div className="dashboard-secondary-main">
              <p className="dashboard-secondary-value">
                {numero.format(indicadores.atendimentos)}
                <small>chamados</small>
              </p>
              <p>Avaliações preenchidas · escala de 1 a 5</p>
            </div>
            <div className="dashboard-secondary-detail">
              <span>Satisfação média</span>
              <strong>
                {indicadores.satisfacao.toLocaleString('pt-BR', {
                  minimumFractionDigits: 1,
                })}{' '}
                / 5
              </strong>
            </div>
          </div>
        </Panel>
      </section>
    </div>
  )
}
