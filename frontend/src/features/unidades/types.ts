/** Contrato JSON de GET /api/unidades/{uc_id}/visao-360.
 * Espelha backend/app/schemas.py; datas são strings no JSON.
 * O backend adapta os nomes da Gold, sem expor seu esquema diretamente à tela.
 */
export interface CadastroUC {
  uc_id: string
  /** Com dados reais, recebe o nome mascarado da Gold. */
  titular: string
  /** Subgrupo tarifário, como B1 ou A4. */
  classe: string
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
}

export type TipoComparacaoContaAlta =
  | 'mes_anterior'
  | 'ano_anterior'
  | 'trimestre_ano_anterior'

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
  /** Query param comparacao; padrão: trimestre_ano_anterior. */
  comparacao: TipoComparacaoContaAlta
  competencias_atuais: string[]
  competencias_referencia: string[]
  /** Valores em kWh. */
  consumo: ComparacaoMetricaUC
  /** Valores em R$, calculados a partir de valor_total. */
  faturamento: ComparacaoMetricaUC
  mensagem: string
}

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
  id_fatura: string | null
  data_pagamento: string | null
  valor_energia: number | null
  valor_total: number | null
}

export interface MedidorUC {
  medidor_id: string
  tipo: string
  data_instalacao: string
  status: string
}

export interface GeracaoDistribuidaUC {
  potencia_kwp: number
  /** Data de conexão: YYYY-MM-DD. */
  data_conexao: string
  fonte: string | null
}

export interface OcorrenciaRedeUC {
  ocorrencia_id: string
  alimentador_id: string
  municipio: string
  /** Data e hora de início em ISO 8601. */
  data: string
  competencia: string
  ucs_afetadas: number
  duracao_h: number
  causa: string | null
  uc_id: string | null
  /** Data e hora de encerramento em ISO 8601, quando disponível. */
  data_fim: string | null
}

export interface InterrupcoesUC {
  alimentador_id: string
  ultimos_12_meses: number
  dec_horas: number | null
  fec_vezes: number | null
  recentes: OcorrenciaRedeUC[]
  /** O serviço atual devolve ocorrências agregadas do alimentador. */
  escopo: 'alimentador' | 'uc'
}

export interface TratativaAtendimentoUC {
  /** O mock usa '—' quando a data é desconhecida. */
  data: string
  descricao: string
}

export interface AtendimentoUC {
  protocolo: string
  /** Data e hora de abertura em ISO 8601. */
  data: string
  canal: string
  assunto: string
  status: string
  nota_satisfacao: number | null
  tratativas: TratativaAtendimentoUC[]
  aberto: boolean | null
  ultima_acao: string | null
}

export interface Visao360 {
  cadastro: CadastroUC
  consumo: ConsumoMensalUC[]
  diagnostico_conta_alta: DiagnosticoContaAltaUC
  faturas: FaturaUC[]
  faturas_em_aberto: FaturaUC[]
  medidor: MedidorUC | null
  geracao_distribuida: GeracaoDistribuidaUC | null
  interrupcoes: InterrupcoesUC
  atendimentos: AtendimentoUC[]
}
