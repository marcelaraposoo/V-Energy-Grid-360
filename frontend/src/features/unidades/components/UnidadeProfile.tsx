import { useId, useRef, useState } from 'react'
import {
  CircleDashed,
  FileText,
  Gauge,
  Headphones,
  Info,
  ScanLine,
  Sun,
  Unplug,
  Zap,
} from 'lucide-react'
import { UnavailableFields } from './UnavailableFields'
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
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const tabPrefix = useId()
  const activeTab = tabs[activeIndex]
  const Section = activeTab.component

  return (
    <div className="ucv-profile">
      <div className="ucv-availability" role="status">
        <Info size={17} aria-hidden="true" />
        <p>
          Consulta disponível em breve. Os dados desta unidade ainda não foram
          consultados.
        </p>
      </div>
      <section
        className="panel ucv-identity"
        aria-labelledby="ucv-identity-title"
      >
        <header className="ucv-identity-header">
          <span className="ucv-identity-icon">
            <ScanLine size={28} strokeWidth={1.5} aria-hidden="true" />
          </span>
          <div>
            <p>Identificador informado</p>
            <h2 id="ucv-identity-title">{id}</h2>
          </div>
          <span className="badge">
            <CircleDashed size={13} aria-hidden="true" />
            Aguardando consulta
          </span>
        </header>
        <UnavailableFields
          labels={[
            'Titular',
            'Classe de consumo',
            'Situação da UC',
            'Logradouro e número',
            'Bairro',
            'Município',
          ]}
        />
      </section>
      <div className="ucv-summary-grid" aria-label="Resumo da unidade">
        {[
          {
            label: 'Consumo mais recente',
            detail: 'Competência ainda não disponível',
            icon: Zap,
          },
          {
            label: 'Valor total da fatura',
            detail: 'Valor em reais (R$)',
            icon: FileText,
          },
          {
            label: 'Faturas em aberto',
            detail: 'Pendências de pagamento',
            icon: CircleDashed,
          },
        ].map(({ label, detail, icon: Icon }) => (
          <section className="panel ucv-summary" key={label}>
            <div>
              <Icon size={17} aria-hidden="true" />
              <h3>{label}</h3>
            </div>
            <p aria-label="Não disponível">—</p>
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
        <Section />
      </div>
    </div>
  )
}
