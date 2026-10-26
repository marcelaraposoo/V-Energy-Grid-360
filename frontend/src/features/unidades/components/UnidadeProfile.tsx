import { useEffect, useId, useRef, useState } from 'react'
import {
  CircleAlert,
  CircleDashed,
  FileText,
  Gauge,
  Headphones,
  LoaderCircle,
  ScanLine,
  Sun,
  Unplug,
  Zap,
} from 'lucide-react'
import { EmptyState } from '../../../components/ui/EmptyState'
import { COMPARACAO_PADRAO, consultarVisao360 } from '../api'
import {
  formatarCompetencia,
  formatarMoeda,
  formatarNumero,
} from '../formatters'
import type { TipoComparacaoContaAlta, Visao360 } from '../types'
import { UnidadeFields } from './UnidadeFields'
import {
  AtendimentosSection,
  ConsumoSection,
  FaturasSection,
  GeracaoSection,
  InterrupcoesSection,
  MedidorSection,
} from './UnidadeSections'

const tabs = [
  { id: 'consumo', label: 'Consumo', icon: Zap, component: ConsumoSection },
  {
    id: 'faturas',
    label: 'Faturas',
    icon: FileText,
    component: FaturasSection,
  },
  { id: 'medidor', label: 'Medidor', icon: Gauge, component: MedidorSection },
  {
    id: 'geracao',
    label: 'Geração solar',
    icon: Sun,
    component: GeracaoSection,
  },
  {
    id: 'interrupcoes',
    label: 'Interrupções',
    icon: Unplug,
    component: InterrupcoesSection,
  },
  {
    id: 'atendimentos',
    label: 'Atendimentos',
    icon: Headphones,
    component: AtendimentosSection,
  },
]

export function UnidadeProfile({ id }: { id: string }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [dados, setDados] = useState<Visao360 | null>(null)
  const [comparacao, setComparacao] =
    useState<TipoComparacaoContaAlta>(COMPARACAO_PADRAO)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [tentativa, setTentativa] = useState(0)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const tabPrefix = useId()
  const activeTab = tabs[activeIndex]
  const Section = activeTab.component
  const tentarNovamente = () => {
    setErro(null)
    setCarregando(true)
    setTentativa((atual) => atual + 1)
  }
  const alterarComparacao = (value: TipoComparacaoContaAlta) => {
    setErro(null)
    setCarregando(true)
    setComparacao(value)
  }

  useEffect(() => {
    const controller = new AbortController()
    consultarVisao360(id, comparacao, controller.signal)
      .then((resposta) => {
        if (controller.signal.aborted) return
        // O filtro atualiza somente o diagnóstico; o histórico mantém sua finalidade.
        setDados((anteriores) =>
          anteriores
            ? {
                ...anteriores,
                diagnostico_conta_alta: resposta.diagnostico_conta_alta,
              }
            : resposta,
        )
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setErro(
          error instanceof Error &&
            !(error instanceof TypeError) &&
            !(error instanceof SyntaxError)
            ? error.message
            : 'Não foi possível carregar os dados. Tente novamente.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setCarregando(false)
      })
    return () => controller.abort()
  }, [id, comparacao, tentativa])

  if (!dados) {
    return (
      <section className="panel" aria-busy={carregando}>
        <div role={erro ? 'alert' : 'status'}>
          <EmptyState
            icon={erro ? CircleAlert : LoaderCircle}
            title={
              erro
                ? 'Consulta não concluída'
                : 'Consultando unidade consumidora'
            }
            description={erro ?? `Carregando os dados de ${id}…`}
          >
            {erro && (
              <button
                type="button"
                className="button button--secondary"
                onClick={tentarNovamente}
              >
                Tentar novamente
              </button>
            )}
          </EmptyState>
        </div>
      </section>
    )
  }

  const cadastro = dados.cadastro
  const ultimoConsumo = dados.consumo.at(-1)
  const ultimaFatura = dados.faturas[0]

  return (
    <div className="ucv-profile">
      <section
        className="panel ucv-identity"
        aria-labelledby="ucv-identity-title"
      >
        <header className="ucv-identity-header">
          <span className="ucv-identity-icon">
            <ScanLine size={28} strokeWidth={1.5} aria-hidden="true" />
          </span>
          <div>
            <p>Unidade consumidora</p>
            <h2 id="ucv-identity-title">{cadastro.uc_id}</h2>
          </div>
          <span className="badge">{cadastro.status}</span>
        </header>
        <UnidadeFields
          fields={[
            { label: 'Titular', value: cadastro.titular },
            {
              label: 'Classe de consumo',
              value: `${cadastro.classe_descricao} (${cadastro.classe})`,
            },
            {
              label: 'Logradouro e número',
              value: cadastro.logradouro
                ? [cadastro.logradouro, cadastro.numero]
                    .filter(Boolean)
                    .join(', ')
                : null,
            },
            { label: 'Bairro', value: cadastro.bairro },
            { label: 'Município', value: cadastro.municipio },
            { label: 'Alimentador', value: cadastro.alimentador_id },
          ]}
        />
      </section>
      <div className="ucv-summary-grid" aria-label="Resumo da unidade">
        {[
          {
            label: 'Consumo mais recente',
            detail: ultimoConsumo
              ? `${formatarCompetencia(ultimoConsumo.competencia)} · kWh`
              : 'Sem histórico de consumo',
            icon: Zap,
            value: formatarNumero(ultimoConsumo?.consumo_kwh),
          },
          {
            label: 'Valor total da fatura',
            detail: ultimaFatura
              ? `Competência ${formatarCompetencia(ultimaFatura.competencia)}`
              : 'Sem fatura disponível',
            icon: FileText,
            value: formatarMoeda(ultimaFatura?.valor_total),
          },
          {
            label: 'Faturas em aberto',
            detail: 'Pendências de pagamento',
            icon: CircleDashed,
            value: formatarNumero(dados.faturas_em_aberto.length),
          },
        ].map(({ label, detail, icon: Icon, value }) => (
          <section className="panel ucv-summary" key={label}>
            <div>
              <Icon size={17} aria-hidden="true" />
              <h3>{label}</h3>
            </div>
            <p>{value}</p>
            <small>{detail}</small>
          </section>
        ))}
      </div>
      <div
        className="ucv-tabs"
        role="tablist"
        aria-label="Informações da unidade consumidora"
      >
        {tabs.map(({ id: tabId, label, icon: Icon }, index) => (
          <button
            key={tabId}
            id={`${tabPrefix}-${tabId}`}
            type="button"
            role="tab"
            aria-selected={activeIndex === index}
            aria-controls={`${tabPrefix}-panel`}
            tabIndex={activeIndex === index ? 0 : -1}
            ref={(element) => {
              tabRefs.current[index] = element
            }}
            onClick={() => setActiveIndex(index)}
            onKeyDown={(event) => {
              let nextIndex: number
              if (event.key === 'ArrowRight')
                nextIndex = (index + 1) % tabs.length
              else if (event.key === 'ArrowLeft')
                nextIndex = (index - 1 + tabs.length) % tabs.length
              else if (event.key === 'Home') nextIndex = 0
              else if (event.key === 'End') nextIndex = tabs.length - 1
              else return
              event.preventDefault()
              setActiveIndex(nextIndex)
              tabRefs.current[nextIndex]?.focus()
            }}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      <div
        id={`${tabPrefix}-panel`}
        role="tabpanel"
        aria-labelledby={`${tabPrefix}-${activeTab.id}`}
        tabIndex={0}
      >
        <Section
          dados={dados}
          comparacao={comparacao}
          onComparacaoChange={alterarComparacao}
          carregando={carregando}
          erro={erro}
          onRetry={tentarNovamente}
        />
      </div>
    </div>
  )
}
