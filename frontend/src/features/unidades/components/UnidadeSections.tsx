import { FileText, Gauge, Headphones, Sun, Unplug } from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { EmptyState } from '../../../components/ui/EmptyState'
import {
  formatarCompetencia,
  formatarData,
  formatarDataHora,
  formatarMoeda,
  formatarNumero,
  formatarNotaSatisfacao,
} from '../formatters'
import type { PeriodoHistorico, SelecaoContaAlta, Visao360 } from '../types'
import { ConsumoChart } from './ConsumoChart'
import { ContaAltaCard } from './ContaAltaCard'
import { HistoryTable } from './HistoryTable'
import { FiltroPeriodoHistorico } from './FiltroPeriodoHistorico'
import { UnidadeFields } from './UnidadeFields'

type SectionProps = { dados: Visao360 }
type ConsumoSectionProps = SectionProps & {
  comparacao: SelecaoContaAlta
  onComparacaoChange: (value: SelecaoContaAlta) => void
  carregando: boolean
  erro: string | null
  onRetry: () => void
}

export function ConsumoSection({
  dados,
  ...diagnosticoProps
}: ConsumoSectionProps) {
  const ultimo = dados.consumo.at(-1)
  const fatura = dados.faturas.find(
    (f) => f.competencia === ultimo?.competencia,
  )

  return (
    <div className="ucv-consumo-grid">
      <div className="ucv-consumo-main">
        <Panel
          title="Histórico de consumo"
          description="Últimos 12 meses disponíveis"
          actions={<span className="badge">kWh</span>}
        >
          <ConsumoChart consumo={dados.consumo} />
        </Panel>
        <Panel
          title="Valor faturado mais recente"
          description={
            ultimo
              ? `Competência ${formatarCompetencia(ultimo.competencia)}`
              : 'Sem competência de consumo disponível'
          }
        >
          <UnidadeFields
            fields={[
              {
                label: 'Valor total da fatura',
                value: formatarMoeda(
                  ultimo?.valor_total ?? fatura?.valor_total,
                ),
              },
              {
                label: 'Mesmo mês do ano anterior',
                value: formatarMoeda(ultimo?.valor_total_ano_anterior),
              },
            ]}
          />
        </Panel>
      </div>
      <ContaAltaCard
        diagnostico={dados.diagnostico_conta_alta}
        {...diagnosticoProps}
      />
    </div>
  )
}

export function FaturasSection({ dados }: SectionProps) {
  const faturas = [
    ...new Map(
      [...dados.faturas, ...dados.faturas_em_aberto].map((f) => [
        f.competencia,
        f,
      ]),
    ).values(),
  ].sort((a, b) => b.competencia.localeCompare(a.competencia))
  const status = { paga: 'Paga', aberta: 'Em aberto', atrasada: 'Atrasada' }

  return (
    <Panel
      title="Faturas e pagamentos"
      description="Últimas faturas e pendências de pagamento, inclusive de competências anteriores"
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
        description="Não há faturas disponíveis para esta unidade."
        empty={!faturas.length}
      >
        {faturas.map((fatura) => (
          <tr key={fatura.competencia}>
            <th scope="row">{formatarCompetencia(fatura.competencia)}</th>
            <td>{formatarMoeda(fatura.valor_energia)}</td>
            <td>{formatarMoeda(fatura.valor_total)}</td>
            <td>{fatura.bandeira}</td>
            <td>{formatarData(fatura.vencimento)}</td>
            <td>{formatarData(fatura.data_pagamento)}</td>
            <td>
              <span className={`badge ucv-fatura--${fatura.status}`}>
                {status[fatura.status]}
              </span>
            </td>
          </tr>
        ))}
      </HistoryTable>
    </Panel>
  )
}

export function MedidorSection({ dados }: SectionProps) {
  const medidor = dados.medidor
  return (
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
  )
}

export function GeracaoSection({ dados }: SectionProps) {
  const geracao = dados.geracao_distribuida
  return (
    <Panel
      title="Geração solar"
      description="Geração distribuída conectada à unidade consumidora"
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
                ]}
              />
            </Panel>
          </>
        )}
      </div>
    </div>
  )
}

type AtendimentosSectionProps = SectionProps & {
  periodoAtendimentos: PeriodoHistorico
  onPeriodoAtendimentosChange: (value: PeriodoHistorico) => void
  carregando: boolean
  erro: string | null
  onRetry: () => void
}

export function AtendimentosSection({
  dados,
  periodoAtendimentos,
  onPeriodoAtendimentosChange,
  carregando,
  erro,
  onRetry,
}: AtendimentosSectionProps) {
  return (
    <div className="ucv-atendimentos">
      <FiltroPeriodoHistorico
        title="Período dos atendimentos"
        value={periodoAtendimentos}
        onChange={onPeriodoAtendimentosChange}
        periodo={dados.periodo_atendimentos}
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
          <Panel
            title="Chamados de atendimento"
            description="Solicitações e últimas ações registradas para a unidade · por data de abertura"
          >
            <HistoryTable
              title="Histórico de chamados de atendimento"
              columns={[
                'Protocolo',
                'Assunto',
                'Subassunto',
                'Canal',
                'Abertura',
                'Fechamento',
                'Situação',
                'Última ação',
                'Satisfação',
              ]}
              icon={Headphones}
              description="Não há chamados registrados para esta unidade no período selecionado."
              empty={!dados.atendimentos.length}
            >
              {dados.atendimentos.map((atendimento) => (
                <tr key={atendimento.protocolo}>
                  <th scope="row">{atendimento.protocolo}</th>
                  <td>{atendimento.assunto}</td>
                  <td>{atendimento.subassunto}</td>
                  <td>{atendimento.canal}</td>
                  <td>{formatarDataHora(atendimento.data)}</td>
                  <td>
                    {atendimento.data_fechamento
                      ? formatarDataHora(atendimento.data_fechamento)
                      : 'Em aberto'}
                  </td>
                  <td>
                    <span
                      className="badge ucv-atendimento"
                      data-status={atendimento.aberto ? 'Em aberto' : 'Fechado'}
                    >
                      {atendimento.aberto ? 'Em aberto' : 'Fechado'}
                    </span>
                  </td>
                  <td>
                    {atendimento.ultima_acao}
                    <small className="ucv-atendimento-detail">
                      {atendimento.qtd_tratativas}{' '}
                      {atendimento.qtd_tratativas === 1
                        ? 'ação registrada'
                        : 'ações registradas'}
                    </small>
                  </td>
                  <td>{formatarNotaSatisfacao(atendimento.nota_satisfacao)}</td>
                </tr>
              ))}
            </HistoryTable>
          </Panel>
        )}
      </div>
    </div>
  )
}
