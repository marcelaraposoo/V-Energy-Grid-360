import {
  ChartColumn,
  CircleHelp,
  FileText,
  Gauge,
  Headphones,
  Sun,
  Unplug,
} from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { EmptyState } from '../../../components/ui/EmptyState'
import { HistoryTable } from './HistoryTable'
import { UnavailableFields } from './UnavailableFields'

export function ConsumoSection() {
  return (
    <div className="ucv-consumo-grid">
      <div className="ucv-consumo-main">
        <Panel
          title="Histórico de consumo"
          description="Últimos 12 meses disponíveis, comparados ao ano anterior"
          actions={<span className="badge">kWh</span>}
        >
          <div className="ucv-chart-placeholder">
            <EmptyState
              icon={ChartColumn}
              title="Consumo ao longo dos meses"
              description="O histórico de consumo e a comparação com o ano anterior ainda não estão disponíveis para esta unidade."
            />
          </div>
          <div className="ucv-chart-legend">
            <span>
              <i className="ucv-legend-dot ucv-legend-dot--accent" />
              Período analisado
            </span>
            <span>
              <i className="ucv-legend-dot" />
              Mesmo período do ano anterior
            </span>
          </div>
        </Panel>
        <Panel
          title="Comparação do valor faturado"
          description="Mesma competência, em anos diferentes"
        >
          <UnavailableFields
            labels={[
              'Valor total da fatura (R$)',
              'Valor total no ano anterior (R$)',
              'Variação (%)',
            ]}
          />
        </Panel>
      </div>
      <section
        className="panel ucv-conta-alta"
        aria-labelledby="ucv-conta-alta-title"
      >
        <header>
          <CircleHelp size={20} strokeWidth={1.6} aria-hidden="true" />
          <h2 id="ucv-conta-alta-title">A conta veio alta?</h2>
        </header>
        <p>Compare o consumo e o valor faturado antes de orientar o cliente.</p>
        <UnavailableFields
          labels={[
            'Variação do consumo (%)',
            'Variação do valor da fatura (%)',
            'Bandeira tarifária',
          ]}
        />
        <div className="ucv-conta-alta-guidance">
          <h3>Uma explicação com contexto</h3>
          <p>
            A análise precisa de dados de períodos equivalentes. Sem esse
            histórico, ainda não é possível avaliar a variação da conta.
          </p>
        </div>
      </section>
    </div>
  )
}

export function FaturasSection() {
  return (
    <Panel
      title="Faturas e pagamentos"
      description="Valores cobrados, vencimentos e situação de pagamento"
    >
      <HistoryTable
        title="Histórico de faturas e pagamentos"
        columns={[
          'Competência',
          'Energia (R$)',
          'Total (R$)',
          'Bandeira',
          'Vencimento',
          'Pagamento',
          'Situação',
        ]}
        icon={FileText}
        description="As faturas e suas informações de pagamento aparecerão aqui quando a consulta estiver disponível."
      />
    </Panel>
  )
}

export function MedidorSection() {
  return (
    <Panel
      title="Medidor atual"
      description="Identificação do equipamento instalado na unidade consumidora"
    >
      <div className="ucv-equipment">
        <span className="ucv-section-icon">
          <Gauge size={28} strokeWidth={1.5} aria-hidden="true" />
        </span>
        <div>
          <h3>Equipamento de medição</h3>
          <p>As informações do medidor ainda não estão disponíveis.</p>
        </div>
      </div>
      <UnavailableFields
        labels={[
          'Identificador do medidor',
          'Tipo do medidor',
          'Data de instalação',
        ]}
      />
    </Panel>
  )
}

export function GeracaoSection() {
  return (
    <Panel
      title="Geração solar"
      description="Geração distribuída conectada à unidade consumidora"
    >
      <div className="ucv-equipment">
        <span className="ucv-section-icon">
          <Sun size={28} strokeWidth={1.5} aria-hidden="true" />
        </span>
        <div>
          <h3>Energia gerada pela unidade</h3>
          <p>A presença de geração solar será informada após a consulta.</p>
        </div>
      </div>
      <UnavailableFields
        labels={[
          'Possui geração solar?',
          'Potência instalada (kWp)',
          'Data de conexão',
        ]}
      />
    </Panel>
  )
}

export function InterrupcoesSection() {
  return (
    <Panel
      title="Interrupções da UC"
      description="Histórico de interrupções de energia da própria unidade consumidora"
    >
      <HistoryTable
        title="Histórico de interrupções da UC"
        columns={['Início', 'Encerramento', 'Duração (min)', 'Causa']}
        icon={Unplug}
        description="O início, a duração e a causa das interrupções aparecerão aqui quando a consulta estiver disponível."
      />
    </Panel>
  )
}

export function AtendimentosSection() {
  return (
    <Panel
      title="Chamados de atendimento"
      description="Solicitações e últimas ações registradas para a unidade"
    >
      <HistoryTable
        title="Histórico de chamados de atendimento"
        columns={[
          'Protocolo',
          'Assunto',
          'Abertura',
          'Situação',
          'Última ação',
          'Satisfação',
        ]}
        icon={Headphones}
        description="Os protocolos, assuntos e detalhes de acompanhamento aparecerão aqui quando a consulta estiver disponível."
      />
    </Panel>
  )
}
