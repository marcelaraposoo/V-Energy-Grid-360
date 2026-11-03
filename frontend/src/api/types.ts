// Tipos que espelham as respostas do backend (backend/app/schemas.py).
// Os nomes dos campos são os mesmos da API (snake_case) para facilitar a conferência com /docs.

export type Competencia = string // 'YYYY-MM'

export type Health = { status: string; data_source: string }

// ---------- filtros e catálogo ----------
export type CatalogoFiltros = {
  municipios: { nome: string; bairros: string[] }[]
  classes: { codigo: string; descricao: string }[]
  alimentadores: { id: string; municipio: string; ucs_total: number }[]
  competencias: Competencia[]
}

export type FiltrosParams = {
  municipio?: string
  bairro?: string
  classe?: string
}

export type PeriodosParams = {
  base_inicio?: Competencia
  base_fim?: Competencia
  atual_inicio?: Competencia
  atual_fim?: Competencia
}

// comparar=false distingue a ausência de comparação dos períodos padrão do case.
export type DashboardParams = FiltrosParams & { indicador?: 'inadimplencia' | 'executivo' } & (
  | (PeriodosParams & { comparar?: true })
  | { comparar: false; atual_inicio?: Competencia; atual_fim?: Competencia; base_inicio?: never; base_fim?: never }
)

// ---------- dashboard e receita ----------
export type Periodo = { inicio: Competencia; fim: Competencia }

export type DetalheInadimplencia = {
  ultima_competencia: Competencia
  ultima_competencia_pct: number | null
  competencias_ausentes: Competencia[]
  competencias_ausentes_base: Competencia[] | null
  data_corte: string
}

export type Kpi = {
  nome: string
  unidade: string
  valor_atual: number | null
  valor_base: number | null
  variacao_abs: number | null
  variacao_pct: number | null
  variacao_pp?: number | null
  inadimplencia?: DetalheInadimplencia | null
}

export type KpisResponse = {
  periodo_base: Periodo | null
  periodo_atual: Periodo
  kpis: Kpi[]
}

export type SeriePonto = {
  competencia: Competencia
  receita: number | null
  energia_kwh: number | null
  tarifa_media: number | null
}

export type CadastroGdMes = {
  competencia: Competencia
  qtd_ucs_cadastradas: number | null
  qtd_ucs_com_gd: number | null
  percentual_gd: number | null
}

export type CadastroGdResponse = {
  atual: CadastroGdMes
  referencia: CadastroGdMes | null
  variacao_cadastradas_pct: number | null
}

export type ClasseConsumo = 'RESIDENCIAL' | 'COMERCIAL' | 'INDUSTRIAL' | 'PODER PUBLICO' | 'RURAL'
export type ConsumoClasse = {
  classe: ClasseConsumo
  consumo_kwh: number | null
  participacao_pct: number | null
  consumo_referencia_kwh: number | null
  variacao_pct: number | null
  competencias_ausentes: Competencia[]
  competencias_ausentes_referencia: Competencia[] | null
}

export type ConsumoClassesResponse = {
  periodo_atual: Periodo
  periodo_base: Periodo | null
  consumo_total_kwh: number | null
  classes: ConsumoClasse[]
}

export type AgruparPor = 'municipio' | 'bairro' | 'classe'

/** Análise de Receita (`GET /api/receita/variacao`). Espelha backend/app/schemas.py.
 * Receita sem tributos (R$) e energia em kWh; nulo = indisponível, nunca zero.
 */
export type VariacaoLinha = {
  /** Município, "Bairro - Município" ou classe; "TOTAL" na linha de total. */
  chave: string
  rotulo: string
  municipio: string | null
  bairro: string | null
  classe: ClasseConsumo | null
  receita_base: number
  receita_atual: number
  variacao_receita: number
  variacao_receita_pct: number | null
  efeito_preco: number
  efeito_volume: number
  energia_base_kwh: number
  energia_atual_kwh: number
  variacao_energia_pct: number | null
  /** Nulo quando o período não tem volume (regra de volume zero da A4). */
  preco_base_kwh: number | null
  preco_atual_kwh: number | null
  /** UCs faturadas na última competência de cada período. */
  qtd_ucs_base: number
  qtd_ucs_atual: number
}

export type FatoresReceita = {
  /** UCs com GD conectada até a última competência do período atual. */
  qtd_ucs_com_gd: number
  /** Volume dessas mesmas UCs em cada período (A2); nulo só sem a A2 exportada. */
  energia_ucs_gd_base_kwh: number | null
  energia_ucs_gd_atual_kwh: number | null
  qtd_trocas_medidor_atual: number
  pct_faturas_bandeira_nao_verde_base: number | null
  pct_faturas_bandeira_nao_verde_atual: number | null
}

export type VariacaoResponse = {
  agrupar_por: AgruparPor
  periodo_base: Periodo
  periodo_atual: Periodo
  /** diagnostico = 2022-07 a 2023-06 × 2025-07 a 2026-06 (contrato da Gold). */
  recorte: 'diagnostico' | 'personalizado'
  total: VariacaoLinha
  /** Ordenadas da maior queda de receita para a maior alta. */
  linhas: VariacaoLinha[]
  fatores: FatoresReceita
  /** Referência e depois o período atual; mês sem dados vem com valores nulos. */
  serie: SeriePonto[]
}

export type VariacaoParams = PeriodosParams &
  FiltrosParams & { agrupar_por?: AgruparPor }

// ---------- unidades consumidoras ----------
/** Contratos JSON da Visão 360 e da consulta paginada de faturas.
 * Espelham backend/app/schemas.py; datas e horários chegam como strings.
 */
export interface CadastroUC {
  uc_id: string
  /** Com dados reais, recebe o nome mascarado da Gold. */
  titular: string
  /** Classe de consumo da Gold, como RESIDENCIAL ou PODER PUBLICO. */
  classe: 'RESIDENCIAL' | 'RURAL' | 'COMERCIAL' | 'PODER PUBLICO' | 'INDUSTRIAL'
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

// Nomes já exportados pelo cliente compartilhado, vinculados ao contrato único acima.
export type UnidadeConsumidora = CadastroUC
export type ConsumoMensal = ConsumoMensalUC
export type DiagnosticoContaAlta = DiagnosticoContaAltaUC
export type Fatura = FaturaUC
export type Medidor = MedidorUC
export type GeracaoDistribuida = GeracaoDistribuidaUC
export type OcorrenciaRede = OcorrenciaRedeUC
export type Interrupcoes = InterrupcoesUC
export type Atendimento = AtendimentoUC

export type BuscarUcParams = {
  q?: string
  municipio?: string
  classe?: string
  limite?: number
}

// ---------- perdas e ordens de inspeção ----------
export type SuspeitaFila = {
  posicao: number
  uc_id: string
  titular: string
  municipio: string
  bairro: string
  classe: string
  motivos: string[]
  probabilidade: number
  energia_recuperavel_kwh_mes: number
  prioridade_score: number
}

export type FilaParams = {
  q?: string
  municipio?: string
  classe?: string
  prob_minima?: number
  pagina?: number
  tamanho?: number
}

// A lista vem no corpo e o total (já com os filtros) no cabeçalho X-Total-Count.
export type Pagina<T> = { itens: T[]; total: number }

export type StatusOrdem = 'PENDENTE' | 'EM_CAMPO' | 'CONCLUIDA' | 'CANCELADA'

// Valores provisórios: serão trocados pelo domínio que a Silver de inspeções definir.
export type TipoIrregularidade =
  | 'fraude'
  | 'ligacao_clandestina'
  | 'erro_leitura'
  | 'erro_cadastro'
  | 'nenhuma'

export type NovaOrdem = {
  uc_id: string
  motivo?: string | null
  observacoes?: string | null
}

export type ResultadoInspecao = {
  tipo: TipoIrregularidade
  energia_recuperada_kwh?: number
  observacoes?: string | null
}

export type Ordem = {
  id: number
  uc_id: string
  status: StatusOrdem
  motivo: string | null
  observacoes: string | null
  criada_em: string
  atualizada_em: string
  resultado: {
    tipo: TipoIrregularidade
    energia_recuperada_kwh: number
    observacoes: string | null
  } | null
}

// ---------- continuidade (DEC/FEC) ----------
export type AlimentadorDecFec = {
  alimentador_id: string
  municipio: string
  dec_horas: number
  fec_vezes: number
  n_ocorrencias: number
  posicao_pior: number
}

export type PontoDecFec = {
  competencia: Competencia
  dec_horas: number
  fec_vezes: number
}

export type ContinuidadeParams = {
  inicio?: Competencia
  fim?: Competencia
}

// ---------- inteligência artificial ----------
export type PerguntaIa = { pergunta: string; sessao_id?: string | null }

// Especificação de gráfico que o agente (Camada 6) devolve; o backend não desenha, só diz o que desenhar.
export type Visualizacao = {
  type: 'line' | 'bar'
  title: string
  x_label?: string | null
  y_label?: string | null
  unit?: string | null
  points: { label: string; value: number }[]
}

export type RespostaIa = {
  status: 'ok' | 'nao_sei' | 'nao_implementado'
  resposta: string
  sql_executado: string | null
  fontes: string[]
  visualizacao?: Visualizacao | null
}

export type TelaInsight =
  | 'dashboard'
  | 'receita'
  | 'unidades'
  | 'perdas'
  | 'continuidade'

export type Insight = {
  tipo: 'destaque' | 'alerta' | 'informativo'
  texto: string
  dados: Record<string, unknown>
}
