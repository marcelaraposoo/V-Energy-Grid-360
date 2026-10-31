/** Contrato JSON de GET /api/unidades/{uc_id}/visao-360.
 * Espelha backend/app/schemas.py; datas são strings no JSON.
 * O backend adapta os nomes da Gold, sem expor seu esquema diretamente à tela.
 */
export interface CadastroUC {
  uc_id: string
  /** Com dados reais, recebe o nome mascarado da Gold. */
  titular: string
  /** Classe de consumo da Gold, como RESIDENCIAL ou PODER PUBLICO. */
  classe: string
  subgrupo_tarifario: 'B1' | 'B2' | 'B3' | 'A4' | null
  classe_descricao: string
  municipio: string
  bairro: string
  alimentador_id: string
  status: string
  data_ligacao: string
  logradouro: string | null
  numero: string | null
  /** null significa indisponível; false significa ausência de GD. */
  possui_gd: boolean | null
}

export interface ConsumoMensalUC {
  /** YYYY-MM */
  competencia: string
  consumo_kwh: number
  consumo_kwh_ano_anterior: number | null
  variacao_consumo_ano_anterior_pct: number | null
  valor_total: number | null
  valor_total_ano_anterior: number | null
  troca_medidor: boolean | null
  troca_medidor_ano_anterior: boolean | null
}

export type ClassificacaoVariacao =
  | 'pequena'
  | 'moderada'
  | 'significativa'
  | 'reducao'

export interface ComparacaoMetricaUC {
  valor_atual: number | null
  valor_referencia: number | null
  variacao_pct: number | null
  classificacao: ClassificacaoVariacao | null
  mensagem: string
}

export interface DiagnosticoContaAltaUC {
  /** Todo o histórico da UC, em ordem crescente, inclusive antes dos últimos 12 meses. */
  competencias_disponiveis: string[]
  /** Padrão: última competência disponível da UC. */
  competencia_atual: string | null
  /** Deve ser anterior ao mês analisado; padrão: competência anterior disponível. */
  competencia_referencia: string | null
  troca_medidor_atual: boolean | null
  troca_medidor_referencia: boolean | null
  /** Valores em kWh. */
  consumo: ComparacaoMetricaUC
  /** Valores em R$, calculados a partir de valor_total. */
  faturamento: ComparacaoMetricaUC
  mensagem: string
}

export type SelecaoContaAlta = Pick<
  DiagnosticoContaAltaUC,
  'competencia_atual' | 'competencia_referencia'
>

export interface FaturaUC {
  uc_id: string
  competencia: string
  municipio: string
  bairro: string
  classe: string
  alimentador_id: string
  consumo_kwh: number
  /** Alias de valor_energia mantido para os serviços de receita e dashboard. */
  valor: number
  bandeira: string
  vencimento: string
  status: 'paga' | 'aberta' | 'atrasada'
  faixa_atraso: 'EM DIA' | 'ATE 30 DIAS' | '31 A 90 DIAS' | 'MAIS DE 90 DIAS'
  id_fatura: string | null
  data_pagamento: string | null
  valor_energia: number | null
  valor_total: number | null
  tributos: number | null
  /** valor_energia / consumo_kwh; inclui bandeira e exclui tributos. */
  preco_medio_kwh: number | null
}

export type AbaFaturas = 'recentes' | 'historico'
export type SituacaoFaturas = 'todas' | 'paga' | 'em_aberto'

export interface ResumoFaturasUC {
  pendencias_recentes: number
  pendencias_antigas: number
}

export interface PaginaFaturasUC {
  itens: FaturaUC[]
  total: number
  pagina: number
  tamanho: 10
  anos_disponiveis: number[]
  resumo: ResumoFaturasUC
}

export interface MedidorUC {
  medidor_id: string
  tipo: string
  data_instalacao: string
  status: string
}

export interface TrocaMedidorUC {
  id_uc: string
  mes_troca: string
  id_medidor_antigo: string
  tipo_medidor_antigo: 'ELETRONICO' | 'ELETROMECANICO' | 'SMART'
  idade_medidor_antigo_anos: number | null
  id_medidor_novo: string
  tipo_medidor_novo: 'ELETRONICO' | 'ELETROMECANICO' | 'SMART'
  consumo_medio_6m_antes: number | null
  consumo_medio_6m_depois: number | null
  variacao_consumo_pct: number | null
  classe: string
  municipio: string
  bairro: string
}

export interface GeracaoDistribuidaUC {
  potencia_kwp: number
  /** Data de conexão: YYYY-MM-DD. */
  data_conexao: string
  /** Modalidade de geração distribuída, conforme dim_uc.modalidade_gd. */
  modalidade: string | null
}

export interface OcorrenciaRedeUC {
  ocorrencia_id: string
  alimentador_id: string
  municipio: string
  bairro: string
  classe: string
  tipo:
    | 'FALTA DE ENERGIA'
    | 'DANO EM EQUIPAMENTO'
    | 'OSCILACAO'
    | 'SOBRECARGA'
    | 'FIO PARTIDO'
  /** Data e hora de início em ISO 8601. */
  data: string
  competencia: string
  duracao_min: number
  causa: CausaInterrupcao | null
  causa_evitavel: boolean
  uc_id: string
  /** Data e hora de encerramento em ISO 8601; a Gold não tem ocorrências em aberto. */
  data_fim: string
}

export type CausaInterrupcao =
  | 'CLIMATICA'
  | 'SOBRECARGA'
  | 'NAO IDENTIFICADA'
  | 'VEGETACAO'
  | 'TERCEIROS'
  | 'FALHA DE EQUIPAMENTO'

export type PeriodoHistorico = '6_meses' | '12_meses' | 'todos'

export interface PeriodoHistoricoUC {
  periodo: PeriodoHistorico
  periodo_inicio: string | null
  periodo_fim: string | null
}

export interface InterrupcoesUC extends PeriodoHistoricoUC {
  alimentador_id: string
  qtd_ocorrencias: number
  /** Duração total das interrupções da própria UC no período selecionado. */
  duracao_total_min: number
  /** Indicadores do alimentador, como contexto da UC. */
  dec_horas: number | null
  fec_vezes: number | null
  qtd_ucs_alimentador_mes: number | null
  competencia_base_ucs: string | null
  /** Impacto do alimentador acumulado no período, em UC × horas. */
  horas_interrompidas: number | null
  historico: OcorrenciaRedeUC[]
  /** Escopo da contagem, duração total e histórico: a própria UC. */
  escopo: 'uc'
}

export interface AtendimentoUC {
  protocolo: string
  uc_id: string
  /** Data e hora de abertura em ISO 8601. */
  data: string
  /** Data e hora de fechamento; nula se estiver em aberto. */
  data_fechamento: string | null
  canal: 'TELEFONE' | 'APP' | 'WHATSAPP' | 'SITE' | 'PRESENCIAL'
  assunto:
    | 'FALTA DE ENERGIA'
    | 'FATURA'
    | 'DANO ELETRICO'
    | 'LIGACAO NOVA'
    | 'GERACAO DISTRIBUIDA'
    | 'RELIGACAO'
  subassunto:
    | 'VISTORIA'
    | 'INTERRUPCAO PARCIAL'
    | 'INTERRUPCAO TOTAL'
    | 'OSCILACAO'
    | 'URGENCIA'
    | 'RESSARCIMENTO'
    | 'APOS PAGAMENTO'
    | 'SOLICITACAO'
    | 'HOMOLOGACAO'
    | 'PRAZO'
    | 'CREDITOS'
    | 'CONTESTACAO'
    | 'SEGUNDA VIA'
    | 'VALOR ALTO'
    | 'PARCELAMENTO'
  /** A situação é determinada por este campo, independentemente da última ação. */
  aberto: boolean
  tempo_resolucao_horas: number | null
  qtd_tratativas: number
  ultima_acao:
    'ABERTURA' | 'ANALISE' | 'DESPACHO' | 'RETORNO AO CLIENTE' | 'ENCERRAMENTO'
  /** Nota de 1 a 5, com uma casa decimal; nula significa não avaliado. */
  nota_satisfacao: number | null
}

export interface Visao360 {
  cadastro: CadastroUC
  consumo: ConsumoMensalUC[]
  diagnostico_conta_alta: DiagnosticoContaAltaUC
  faturas: FaturaUC[]
  resumo_faturas: ResumoFaturasUC
  medidor: MedidorUC | null
  trocas_medidor: TrocaMedidorUC[]
  geracao_distribuida: GeracaoDistribuidaUC | null
  interrupcoes: InterrupcoesUC
  periodo_atendimentos: PeriodoHistoricoUC
  atendimentos: AtendimentoUC[]
}
