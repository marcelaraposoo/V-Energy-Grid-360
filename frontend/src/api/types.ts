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

// ---------- dashboard e receita ----------
export type Periodo = { inicio: Competencia; fim: Competencia }

export type Kpi = {
  nome: string
  unidade: string
  valor_atual: number
  valor_base: number
  variacao_abs: number
  variacao_pct: number | null
}

export type KpisResponse = {
  periodo_base: Periodo
  periodo_atual: Periodo
  kpis: Kpi[]
}

export type SeriePonto = {
  competencia: Competencia
  receita: number
  energia_kwh: number
  tarifa_media: number
}

export type AgruparPor = 'municipio' | 'bairro' | 'classe'

export type VariacaoLinha = {
  chave: string
  receita_base: number
  receita_atual: number
  variacao_receita: number
  efeito_preco: number
  efeito_volume: number
  energia_base_kwh: number
  energia_atual_kwh: number
  variacao_energia_pct: number | null
}

export type VariacaoResponse = {
  agrupar_por: AgruparPor
  periodo_base: Periodo
  periodo_atual: Periodo
  total: VariacaoLinha
  linhas: VariacaoLinha[]
}

export type VariacaoParams = PeriodosParams &
  FiltrosParams & { agrupar_por?: AgruparPor }

// ---------- unidades consumidoras ----------
export type UnidadeConsumidora = {
  uc_id: string
  titular: string
  classe: string
  classe_descricao: string
  municipio: string
  bairro: string
  alimentador_id: string
  status: string
  data_ligacao: string
}

export type BuscarUcParams = {
  q?: string
  municipio?: string
  classe?: string
  limite?: number
}

export type ConsumoMensal = {
  competencia: Competencia
  consumo_kwh: number
  consumo_kwh_ano_anterior: number | null
}

export type DiagnosticoContaAlta = {
  consumo_subiu: boolean | null
  variacao_pct: number | null
  mensagem: string
}

// No backend atual o status é paga | aberta | atrasada. Na Gold real virá PAGA / EM ABERTO,
// e "atrasada" será derivada do vencimento.
export type Fatura = {
  uc_id: string
  competencia: Competencia
  municipio: string
  bairro: string
  classe: string
  alimentador_id: string
  consumo_kwh: number
  valor: number
  bandeira: string
  vencimento: string
  status: string
}

export type Medidor = {
  medidor_id: string
  tipo: string
  data_instalacao: string
  status: string
}

export type GeracaoDistribuida = {
  potencia_kwp: number
  data_conexao: string
  fonte: string
}

export type OcorrenciaRede = {
  ocorrencia_id: string
  alimentador_id: string
  municipio: string
  data: string
  competencia: Competencia
  ucs_afetadas: number
  duracao_h: number
  causa: string
}

export type Interrupcoes = {
  alimentador_id: string
  ultimos_12_meses: number
  dec_horas: number
  fec_vezes: number
  recentes: OcorrenciaRede[]
}

export type Atendimento = {
  protocolo: string
  data: string
  canal: string
  assunto: string
  status: string
  nota_satisfacao: number | null
  tratativas: { data: string; descricao: string }[]
}

export type Visao360 = {
  cadastro: UnidadeConsumidora
  consumo: ConsumoMensal[]
  diagnostico_conta_alta: DiagnosticoContaAlta
  faturas: Fatura[]
  faturas_em_aberto: Fatura[]
  medidor: Medidor | null
  geracao_distribuida: GeracaoDistribuida | null
  interrupcoes: Interrupcoes
  atendimentos: Atendimento[]
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
