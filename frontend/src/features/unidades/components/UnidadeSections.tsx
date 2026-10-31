import { FileText, Gauge, Sun, Unplug } from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { EmptyState } from '../../../components/ui/EmptyState'
import {
  formatarCompetencia,
  formatarData,
  formatarDataHora,
  formatarMoeda,
  formatarPrecoKwh,
  formatarNumero,
  situacoesFatura,
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
  const fatura = dados.faturas[0]

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
          title="Detalhamento da última fatura"
          className="ucv-fatura-detalhe"
          description={
            fatura
              ? `Competência ${formatarCompetencia(fatura.competencia)}`
              : 'Sem fatura disponível'
          }
          actions={
            fatura && (
              <span className={`badge ucv-fatura--${fatura.status}`}>
                {situacoesFatura[fatura.status]}
              </span>
            )
          }
        >
          {fatura ? (
            <>
              <p className="ucv-fatura-total">
                <span>Valor total da fatura</span>
                <strong>{formatarMoeda(fatura.valor_total)}</strong>
              </p>
              <UnidadeFields
                fields={[
                  {
                    label: 'Consumo faturado (kWh)',
                    value: formatarNumero(fatura.consumo_kwh),
                  },
                  {
                    label: 'Energia',
                    value: formatarMoeda(fatura.valor_energia),
                  },
                  { label: 'Tributos', value: formatarMoeda(fatura.tributos) },
                  {
                    label: 'Preço médio por kWh',
                    value: formatarPrecoKwh(fatura.preco_medio_kwh),
                  },
                  { label: 'Bandeira tarifária', value: fatura.bandeira },
                  { label: 'Vencimento', value: formatarData(fatura.vencimento) },
                ]}
              />
              <p className="ucv-fatura-note">
                O valor da energia e o preço médio por kWh incluem o adicional
                de bandeira e não incluem tributos.
              </p>
            </>
          ) : (
            <EmptyState
              icon={FileText}
              title="Sem fatura disponível"
              description="Não há dados de faturamento para esta unidade."
            />
          )}
        </Panel>
      </div>
      <ContaAltaCard
        diagnostico={dados.diagnostico_conta_alta}
        {...diagnosticoProps}
      />
    </div>
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
