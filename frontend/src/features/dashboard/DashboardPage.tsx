import { useState } from 'react'
import {
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  CircleDollarSign,
  Headphones,
  RotateCcw,
  Sun,
  Users,
  Wallet,
  Zap,
} from 'lucide-react'
import { PageHeader } from '../../components/ui/PageHeader'
import { Panel } from '../../components/ui/Panel'
import { EvolucaoChart } from './EvolucaoChart'
import { SeletorPeriodo } from './SeletorPeriodo'
import { SeletorFiltro } from './SeletorFiltro'
import type { PeriodoSelecionado } from './SeletorPeriodo'
import { dashboardMock, locaisMock } from './mockData'
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
const { atual, referencia, indicadores } = dashboardMock
const periodoPadrao = { inicio: atual.inicio, fim: atual.fim }

function periodoAnoAnterior(
  periodo: PeriodoSelecionado,
): PeriodoSelecionado | null {
  const anterior = (mes: string) =>
    `${Number(mes.slice(0, 4)) - 1}${mes.slice(4)}`
  const inicio = anterior(periodo.inicio)
  const fim = anterior(periodo.fim)
  return inicio < dashboardMock.inicioBase ? null : { inicio, fim }
}

const receitaAtual = total(atual.receita)
const receitaReferencia = total(referencia.receita)
const consumoAtual = total(atual.consumo)
const consumoReferencia = total(referencia.consumo)

const kpis = [
  {
    label: 'Receita faturada',
    icon: Banknote,
    valor: `R$ ${compacto.format(receitaAtual)}`,
    detalhe: 'Valor da energia, sem tributos',
    atual: receitaAtual,
    referencia: receitaReferencia,
  },
  {
    label: 'Consumo faturado',
    icon: Zap,
    valor: `${compacto.format(consumoAtual)} kWh`,
    detalhe: 'Energia faturada no período',
    atual: consumoAtual,
    referencia: consumoReferencia,
  },
  {
    label: 'UCs faturadas',
    icon: Users,
    valor: numero.format(indicadores.ucsFaturadas),
    detalhe: 'Jun/2026 · unidades com fatura no mês',
    atual: indicadores.ucsFaturadas,
    referencia: indicadores.ucsFaturadasReferencia,
  },
  {
    label: 'Preço médio por kWh',
    icon: CircleDollarSign,
    valor: moeda.format(receitaAtual / consumoAtual),
    detalhe: 'Receita de energia / consumo faturado',
    atual: receitaAtual / consumoAtual,
    referencia: receitaReferencia / consumoReferencia,
  },
]

export function DashboardPage() {
  const [municipio, setMunicipio] = useState('')
  const [bairro, setBairro] = useState('')
  const [classe, setClasse] = useState('')
  const [periodo, setPeriodo] = useState(periodoPadrao)
  const [comparacao, setComparacao] = useState(() =>
    periodoAnoAnterior(periodoPadrao),
  )
  const bairros =
    locaisMock.find((local) => local.municipio === municipio)?.bairros ?? []

  return (
    <div className="dashboard-page">
      <PageHeader
        eyebrow="VISÃO GERAL"
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
          setPeriodo(periodoPadrao)
          setComparacao(periodoAnoAnterior(periodoPadrao))
        }}
      >
        <SeletorPeriodo
          label="Período analisado"
          valor={periodo}
          minimo={dashboardMock.inicioBase}
          maximo={atual.fim}
          onChange={(selecionado) => {
            setPeriodo(selecionado)
            setComparacao(periodoAnoAnterior(selecionado))
          }}
        />
        <SeletorPeriodo
          label="Período de comparação"
          valor={comparacao}
          minimo={dashboardMock.inicioBase}
          maximo={atual.fim}
          onChange={setComparacao}
        />
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
      </form>

      <section className="dashboard-kpis" aria-label="Indicadores principais">
        {kpis.map(
          ({ label, icon: Icon, valor, detalhe, atual, referencia }) => {
            const variacao = (atual / referencia - 1) * 100
            const Seta = variacao < 0 ? ArrowDownRight : ArrowUpRight
            return (
              <article className="panel dashboard-kpi" key={label}>
                <h2>
                  <Icon size={17} strokeWidth={1.5} aria-hidden="true" />
                  {label}
                </h2>
                <p className="dashboard-kpi-value">{valor}</p>
                <p className="dashboard-kpi-detail">{detalhe}</p>
                <p className="dashboard-kpi-comparison">
                  <span>
                    <Seta size={15} aria-hidden="true" />
                    {percentual.format(variacao)}%
                  </span>
                  vs. referência
                </p>
              </article>
            )
          },
        )}
      </section>

      <div className="dashboard-charts">
        <Panel
          title="Evolução da receita"
          description="Receita de energia, sem tributos · R$ milhões"
        >
          <EvolucaoChart
            titulo="Receita mensal"
            unidade="R$"
            atual={atual.receita}
            referencia={referencia.receita}
          />
        </Panel>
        <Panel
          title="Evolução do consumo"
          description="Energia faturada · milhões de kWh"
        >
          <EvolucaoChart
            titulo="Consumo mensal"
            unidade="kWh"
            atual={atual.consumo}
            referencia={referencia.consumo}
          />
        </Panel>
      </div>

      <section
        className="dashboard-secondary"
        aria-label="Indicadores complementares"
      >
        <Panel
          title="Inadimplência"
          description="Faturas da competência Jun/2026"
          actions={<Wallet size={18} aria-hidden="true" />}
        >
          <div className="dashboard-secondary-body">
            <p className="dashboard-secondary-value">
              {indicadores.inadimplencia.toLocaleString('pt-BR')}
              <small>%</small>
            </p>
            <p>Do valor total da competência em aberto</p>
            <div className="dashboard-secondary-detail">
              <span>Faturas em aberto</span>
              <strong>{numero.format(indicadores.faturasEmAberto)}</strong>
            </div>
          </div>
        </Panel>
        <Panel
          title="Geração distribuída"
          description="Conectada até Jun/2026"
          actions={<Sun size={18} aria-hidden="true" />}
        >
          <div className="dashboard-secondary-body">
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
            <p className="dashboard-secondary-value">
              {numero.format(indicadores.atendimentos)}
              <small>chamados</small>
            </p>
            <p>Avaliações preenchidas · escala de 1 a 5</p>
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
