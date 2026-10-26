import { FileText, Gauge, Headphones, Sun, Unplug } from 'lucide-react'
import { Panel } from '../../../components/ui/Panel'
import { EmptyState } from '../../../components/ui/EmptyState'
import {
  formatarCompetencia,
  formatarData,
  formatarDataHora,
  formatarMoeda,
  formatarNumero,
} from '../formatters'
import type { TipoComparacaoContaAlta, Visao360 } from '../types'
import { ConsumoChart } from './ConsumoChart'
import { ContaAltaCard } from './ContaAltaCard'
import { HistoryTable } from './HistoryTable'
import { UnidadeFields } from './UnidadeFields'

type SectionProps = { dados: Visao360 }
type ConsumoSectionProps = SectionProps & {
  comparacao: TipoComparacaoContaAlta
  onComparacaoChange: (value: TipoComparacaoContaAlta) => void
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
              <span className="badge">{status[fatura.status]}</span>
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
            { label: 'Situação', value: medidor.status },
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
            { label: 'Possui geração solar?', value: 'Sim' },
            {
              label: 'Potência instalada (kWp)',
              value: formatarNumero(geracao.potencia_kwp),
            },
            {
              label: 'Data de conexão',
              value: formatarData(geracao.data_conexao),
            },
            { label: 'Fonte', value: geracao.fonte },
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

export function InterrupcoesSection({ dados }: SectionProps) {
  const interrupcoes = dados.interrupcoes
  const escopo =
    interrupcoes.escopo === 'alimentador' ? 'do alimentador' : 'da UC'
  return (
    <Panel
      title={`Interrupções ${escopo}`}
      description={
        interrupcoes.escopo === 'alimentador'
          ? `Ocorrências do alimentador ${interrupcoes.alimentador_id}. A ocorrência individual nesta UC não está confirmada por esses registros.`
          : 'Histórico de interrupções da própria unidade consumidora'
      }
    >
      <UnidadeFields
        fields={[
          {
            label: 'Ocorrências nos últimos 12 meses',
            value: formatarNumero(interrupcoes.ultimos_12_meses),
          },
          {
            label: 'DEC do alimentador (horas)',
            value: formatarNumero(interrupcoes.dec_horas),
          },
          {
            label: 'FEC do alimentador',
            value: formatarNumero(interrupcoes.fec_vezes),
          },
        ]}
      />
      <HistoryTable
        title={`Ocorrências recentes ${escopo}`}
        columns={['Início', 'Encerramento', 'Duração (min)', 'Causa']}
        icon={Unplug}
        description="Não há ocorrências recentes disponíveis no período consultado."
        empty={!interrupcoes.recentes.length}
      >
        {interrupcoes.recentes.map((ocorrencia) => (
          <tr key={ocorrencia.ocorrencia_id}>
            <th scope="row">{formatarDataHora(ocorrencia.data)}</th>
            <td>{formatarDataHora(ocorrencia.data_fim)}</td>
            <td>{formatarNumero(ocorrencia.duracao_h * 60)}</td>
            <td>{ocorrencia.causa ?? 'Não informada'}</td>
          </tr>
        ))}
      </HistoryTable>
    </Panel>
  )
}

export function AtendimentosSection({ dados }: SectionProps) {
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
          'Canal',
          'Abertura',
          'Situação',
          'Última ação',
          'Satisfação',
        ]}
        icon={Headphones}
        description="Não há chamados registrados para esta unidade."
        empty={!dados.atendimentos.length}
      >
        {dados.atendimentos.map((atendimento) => (
          <tr key={atendimento.protocolo}>
            <th scope="row">{atendimento.protocolo}</th>
            <td>{atendimento.assunto}</td>
            <td>{atendimento.canal}</td>
            <td>{formatarDataHora(atendimento.data)}</td>
            <td>{atendimento.status}</td>
            <td>
              {atendimento.ultima_acao ??
                atendimento.tratativas.at(-1)?.descricao ??
                'Não disponível'}
            </td>
            <td>{formatarNumero(atendimento.nota_satisfacao)}</td>
          </tr>
        ))}
      </HistoryTable>
    </Panel>
  )
}
