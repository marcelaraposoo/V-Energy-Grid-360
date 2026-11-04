import { ArrowRight, Gauge, Sun, Unplug } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Panel } from '../../../components/ui/Panel'
import { InfoTipContent } from '../../../components/ui/InfoTip'
import { EmptyState } from '../../../components/ui/EmptyState'
import {
  formatarCompetencia,
  formatarData,
  formatarDataHora,
  formatarNumero,
  formatarPercentual,
} from '../formatters'
import type { PeriodoHistorico, Visao360 } from '../types'
import { ConsumoChart } from './ConsumoChart'
import { InsightsUcCard } from './InsightsUcCard'
import { HistoryTable } from './HistoryTable'
import { FiltroPeriodoHistorico } from './FiltroPeriodoHistorico'
import { UnidadeFields } from './UnidadeFields'

type SectionProps = { dados: Visao360 }

export function ConsumoSection({ dados }: SectionProps) {
  return (
    <div className="ucv-consumo-grid">
      <div className="ucv-consumo-main">
        <Panel
          title="Histórico de consumo"
          description="Últimos 12 meses disponíveis"
          info={<InfoTipContent resumo="Consumo mensal da unidade, comparado ao mesmo mês do ano anterior."
            nota="Passe sobre as barras para ver os valores. A ausência de referência significa que não há leitura para comparação." />}
          actions={<span className="badge">kWh</span>}
        >
          <ConsumoChart consumo={dados.consumo} />
        </Panel>
      </div>
      {/* Substitui o "A conta veio alta?": a leitura do consumo × valor cobrado agora vem dos insights. */}
      <InsightsUcCard ucId={dados.cadastro.uc_id} competencias={dados.diagnostico_conta_alta.competencias_disponiveis} />
    </div>
  )
}

export function MedidorSection({ dados }: SectionProps) {
  const medidor = dados.medidor
  return (
    <div className="ucv-medidores">
      <Panel
        title="Medidor atual"
        description="Equipamento instalado na unidade consumidora"
        className="ucv-medidor"
      >
        {medidor ? (
          <UnidadeFields
            fields={[
              { label: 'Identificador do medidor', value: medidor.medidor_id },
              { label: 'Tipo do medidor', value: medidor.tipo },
              {
                label: 'Data de instalação',
                value: formatarData(medidor.data_instalacao),
              },
              { label: 'Situação', value: medidor.status.toUpperCase() },
            ]}
          />
        ) : (
          <EmptyState
            icon={Gauge}
            title="Medidor não disponível"
            description="Não há informações do medidor instalado nesta unidade."
          />
        )}
      </Panel>
      <Panel title="Histórico de trocas de medidor" description="Médias de consumo antes e depois de cada troca"
        info={<InfoTipContent resumo="Compare o consumo médio antes e depois da troca do equipamento." itens={[
          { rotulo: 'Antes', texto: 'Seis meses anteriores à troca.' },
          { rotulo: 'Depois', texto: 'Até seis meses posteriores, conforme o histórico disponível.' },
        ]} nota="O mês da troca fica fora das médias. A variação, sozinha, não comprova a causa da mudança." />}>
        {dados.trocas_medidor.length ? (
          <>
            <HistoryTable title="Trocas de medidor da UC"
              columns={['Competência', 'Medidor retirado', 'Medidor instalado', 'Média antes (kWh)', 'Média depois (kWh)', 'Variação']}
              icon={Gauge} description="Não há trocas de medidor registradas para esta unidade." empty={false}>
              {dados.trocas_medidor.map(troca => (
                <tr key={`${troca.mes_troca}-${troca.id_medidor_novo}`}>
                  <th scope="row">{formatarCompetencia(troca.mes_troca)}</th>
                  <td>
                    {troca.id_medidor_antigo}
                    <small className="ucv-medidor-detail">{troca.tipo_medidor_antigo}</small>
                    <small className="ucv-medidor-detail">
                      Idade na retirada: {troca.idade_medidor_antigo_anos === null
                        ? 'Não disponível' : `${formatarNumero(troca.idade_medidor_antigo_anos)} anos`}
                    </small>
                  </td>
                  <td>
                    {troca.id_medidor_novo}
                    <small className="ucv-medidor-detail">{troca.tipo_medidor_novo}</small>
                  </td>
                  <td>{formatarNumero(troca.consumo_medio_6m_antes)}</td>
                  <td>{formatarNumero(troca.consumo_medio_6m_depois)}</td>
                  <td>{formatarPercentual(troca.variacao_consumo_pct)}</td>
                </tr>
              ))}
            </HistoryTable>
            <p className="ucv-troca-note">Médias dos seis meses anteriores e de até seis meses posteriores, sem incluir o mês da troca. </p>
          </>
        ) : <EmptyState compact icon={Gauge} title="Sem trocas de medidor" description="Não há trocas de medidor registradas para esta unidade." />}
      </Panel>
    </div>
  )
}

export function GeracaoSection({ dados }: SectionProps) {
  const geracao = dados.geracao_distribuida
  return (
    <Panel
      title="Geração solar"
      description="Geração distribuída conectada à unidade consumidora"
      info={<InfoTipContent resumo="Dados da geração solar conectada a esta unidade." itens={[
        { rotulo: 'Potência (kWp)', texto: 'Capacidade instalada dos painéis; não é a energia gerada por mês.' },
        { rotulo: 'Conexão', texto: 'Data de entrada da geração distribuída na rede.' },
      ]} />}
    >
      {geracao ? (
        <UnidadeFields
          fields={[
            {
              label: 'Potência instalada (kWp)',
              value: formatarNumero(geracao.potencia_kwp),
            },
            {
              label: 'Data de conexão',
              value: formatarData(geracao.data_conexao),
            },
            { label: 'Modalidade', value: geracao.modalidade },
          ]}
        />
      ) : (
        <EmptyState
          icon={Sun}
          title={
            dados.cadastro.possui_gd === false
              ? 'Sem geração solar'
              : 'Geração solar não disponível'
          }
          description={
            dados.cadastro.possui_gd === false
              ? 'Esta unidade não possui geração distribuída.'
              : 'Não há informações de geração distribuída disponíveis para esta unidade.'
          }
        />
      )}
    </Panel>
  )
}

type InterrupcoesSectionProps = SectionProps & {
  periodoInterrupcoes: PeriodoHistorico
  onPeriodoInterrupcoesChange: (value: PeriodoHistorico) => void
  carregando: boolean
  erro: string | null
  onRetry: () => void
}

export function InterrupcoesSection({
  dados,
  periodoInterrupcoes,
  onPeriodoInterrupcoesChange,
  carregando,
  erro,
  onRetry,
}: InterrupcoesSectionProps) {
  const interrupcoes = dados.interrupcoes
  const periodo =
    interrupcoes.periodo_inicio && interrupcoes.periodo_fim
      ? `${formatarCompetencia(interrupcoes.periodo_inicio)} a ${formatarCompetencia(interrupcoes.periodo_fim)}`
      : 'Período não disponível'
  return (
    <div className="ucv-interrupcoes">
      <FiltroPeriodoHistorico
        title="Período das interrupções"
        value={periodoInterrupcoes}
        onChange={onPeriodoInterrupcoesChange}
        periodo={interrupcoes}
        carregando={carregando}
        erro={erro}
      />
      <div
        className="ucv-history-results"
        aria-busy={carregando}
        aria-live="polite"
      >
        {erro ? (
          <div role="alert" className="ucv-diagnostic-error">
            <p>{erro}</p>
            <button
              type="button"
              className="button button--secondary"
              onClick={onRetry}
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <>
            <Panel
              title="Interrupções da UC"
              description={`Ocorrências da própria unidade consumidora · ${periodo}`}
              info={<InfoTipContent resumo="Faltas de energia registradas para esta unidade no período selecionado."
                nota="A duração soma os minutos das ocorrências da UC. Os indicadores do alimentador aparecem no card ao lado." />}
            >
              <UnidadeFields
                fields={[
                  {
                    label: 'Quantidade de ocorrências',
                    value: formatarNumero(interrupcoes.qtd_ocorrencias),
                  },
                  {
                    label: 'Duração total das interrupções (min)',
                    value: formatarNumero(interrupcoes.duracao_total_min),
                  },
                ]}
              />
              <HistoryTable
                title="Histórico de interrupções da UC"
                columns={['Início', 'Fim', 'Duração (min)', 'Tipo', 'Causa']}
                icon={Unplug}
                description="Não há interrupções registradas para esta UC no período selecionado."
                empty={!interrupcoes.historico.length}
              >
                {interrupcoes.historico.map((ocorrencia) => (
                  <tr key={ocorrencia.ocorrencia_id}>
                    <th scope="row">{formatarDataHora(ocorrencia.data)}</th>
                    <td>{formatarDataHora(ocorrencia.data_fim)}</td>
                    <td>{formatarNumero(ocorrencia.duracao_min)}</td>
                    <td>{ocorrencia.tipo}</td>
                    <td>{ocorrencia.causa ?? 'Não informada'}</td>
                  </tr>
                ))}
              </HistoryTable>
            </Panel>
            <Panel
              title="Contexto do alimentador"
              description={`Indicadores acumulados no mesmo período · ${periodo}`}
              info={<InfoTipContent resumo="Qualidade do circuito que abastece a unidade." itens={[
                { rotulo: 'DEC · duração', texto: 'Horas equivalentes sem energia por unidade consumidora.' },
                { rotulo: 'FEC · frequência', texto: 'Número equivalente de interrupções por unidade consumidora.' },
                { rotulo: 'Impacto · UC × horas', texto: 'Soma das horas sem energia de todas as unidades afetadas.' },
              ]} nota="São indicadores do alimentador inteiro, não apenas desta UC. A competência informa a base de unidades usada." />}
              actions={interrupcoes.alimentador_id ? <Link className="link-button ucv-link-qualidade"
                to={`/qualidade?alimentador=${encodeURIComponent(interrupcoes.alimentador_id)}`}>
                Ver na Qualidade do Serviço <ArrowRight size={13} aria-hidden="true" />
              </Link> : undefined}
            >
              <UnidadeFields
                fields={[
                  { label: 'Alimentador', value: interrupcoes.alimentador_id },
                  {
                    label: 'DEC acumulado (horas)',
                    value: formatarNumero(interrupcoes.dec_horas),
                  },
                  {
                    label: 'FEC acumulado',
                    value: formatarNumero(interrupcoes.fec_vezes),
                  },
                  {
                    label: 'UCs do alimentador',
                    value: formatarNumero(interrupcoes.qtd_ucs_alimentador_mes),
                  },
                  {
                    label: 'Competência da base de UCs',
                    value: interrupcoes.competencia_base_ucs
                      ? formatarCompetencia(interrupcoes.competencia_base_ucs)
                      : 'Não disponível',
                  },
                  {
                    label: 'Impacto acumulado (UC × horas)',
                    value: formatarNumero(interrupcoes.horas_interrompidas),
                  },
                ]}
              />
            </Panel>
          </>
        )}
      </div>
    </div>
  )
}
