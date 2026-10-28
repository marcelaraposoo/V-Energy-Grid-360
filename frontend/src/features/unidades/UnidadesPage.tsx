import {
  CircleAlert,
  FileText,
  Gauge,
  Headphones,
  ScanLine,
  Sun,
  Unplug,
  Zap,
} from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { UnitSearch } from '../../components/ui/UnitSearch'
import {
  identificadorUCValido,
  normalizarIdentificadorUC,
} from '../../utils/uc'
import { UnidadeProfile } from './components/UnidadeProfile'
import './unidades.css'

const areas = [
  { label: 'Consumo', description: 'Comparação com o ano anterior', icon: Zap },
  { label: 'Faturas', description: 'Valores e pagamentos', icon: FileText },
  { label: 'Medidor', description: 'Equipamento instalado', icon: Gauge },
  { label: 'Geração solar', description: 'Potência e conexão', icon: Sun },
  {
    label: 'Interrupções',
    description: 'Histórico de fornecimento',
    icon: Unplug,
  },
  {
    label: 'Atendimentos',
    description: 'Chamados e últimas ações',
    icon: Headphones,
  },
]

export function UnidadesPage() {
  const { id: routeId } = useParams()
  const id = routeId ? normalizarIdentificadorUC(routeId) : null

  return (
    <div className="ucv-page">
      <PageHeader
        eyebrow="ANÁLISES · ATENDIMENTO"
        title="Visão 360 da UC"
        description="Cadastro, consumo e histórico do cliente em um só lugar."
      />
      <section
        className="panel ucv-search-panel"
        aria-label="Localizar unidade consumidora"
      >
        <div>
          <h2>Qual unidade você procura?</h2>
          <p>
            Informe UC seguido de seis dígitos, conforme o identificador da
            conta.
          </p>
        </div>
        <UnitSearch key={id ?? 'busca'} />
      </section>
      {!id ? (
        <section className="panel ucv-search-empty">
          <EmptyState
            icon={ScanLine}
            title="Comece pela unidade consumidora"
            description="Localize uma UC para acompanhar o cadastro, entender o consumo e consultar o histórico de atendimento."
          />
          <div className="ucv-area-grid">
            {areas.map(({ label, description, icon: Icon }) => (
              <div key={label}>
                <Icon size={20} strokeWidth={1.5} aria-hidden="true" />
                <strong>{label}</strong>
                <small>{description}</small>
              </div>
            ))}
          </div>
        </section>
      ) : !identificadorUCValido(id) ? (
        <section className="panel">
          <EmptyState
            icon={CircleAlert}
            title="Identificador inválido"
            description="O identificador deve conter UC seguido de seis dígitos, como UC100000."
          >
            <Link to="/uc" className="button button--secondary">
              Voltar à busca
            </Link>
          </EmptyState>
        </section>
      ) : (
        <UnidadeProfile key={id} id={id} />
      )}
    </div>
  )
}
