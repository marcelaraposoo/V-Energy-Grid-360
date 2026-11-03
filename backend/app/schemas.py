from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Competencia = str  # "YYYY-MM"


class Periodo(BaseModel):
    inicio: Competencia
    fim: Competencia


class Filtros(BaseModel):
    municipio: str | None = None
    bairro: str | None = None
    classe: str | None = None


# ---------- dashboard / receita ----------
class DetalheInadimplencia(BaseModel):
    ultima_competencia: Competencia
    ultima_competencia_pct: float | None
    competencias_ausentes: list[Competencia]
    competencias_ausentes_base: list[Competencia] | None
    data_corte: date


class Kpi(BaseModel):
    nome: str
    unidade: str
    valor_atual: float | None
    valor_base: float | None
    variacao_abs: float | None
    variacao_pct: float | None
    variacao_pp: float | None = None
    inadimplencia: DetalheInadimplencia | None = None


class KpisResponse(BaseModel):
    periodo_base: Periodo | None
    periodo_atual: Periodo
    kpis: list[Kpi]


class SeriePonto(BaseModel):
    competencia: Competencia
    receita: float | None
    energia_kwh: float | None
    tarifa_media: float | None


class CadastroGdMes(BaseModel):
    competencia: Competencia
    qtd_ucs_cadastradas: int | None
    qtd_ucs_com_gd: int | None
    percentual_gd: float | None


class CadastroGdResponse(BaseModel):
    atual: CadastroGdMes
    referencia: CadastroGdMes | None
    variacao_cadastradas_pct: float | None


ClasseConsumo = Literal["RESIDENCIAL", "COMERCIAL", "INDUSTRIAL", "PODER PUBLICO", "RURAL"]


class ConsumoClasse(BaseModel):
    classe: ClasseConsumo
    consumo_kwh: float | None
    participacao_pct: float | None
    consumo_referencia_kwh: float | None
    variacao_pct: float | None
    competencias_ausentes: list[Competencia]
    competencias_ausentes_referencia: list[Competencia] | None


class ConsumoClassesResponse(BaseModel):
    periodo_atual: Periodo
    periodo_base: Periodo | None
    consumo_total_kwh: float | None
    classes: list[ConsumoClasse]


class VariacaoLinha(BaseModel):
    chave: str
    rotulo: str = Field(description="Nome de exibição: município, bairro ou descrição da classe.")
    municipio: str | None
    bairro: str | None
    classe: ClasseConsumo | None
    receita_base: float
    receita_atual: float
    variacao_receita: float
    variacao_receita_pct: float | None
    efeito_preco: float
    efeito_volume: float
    energia_base_kwh: float
    energia_atual_kwh: float
    variacao_energia_pct: float | None
    preco_base_kwh: float | None = Field(description="Receita / energia; nulo sem volume no período (regra da A4).")
    preco_atual_kwh: float | None
    qtd_ucs_base: int = Field(ge=0, description="UCs faturadas na última competência do período de referência.")
    qtd_ucs_atual: int = Field(ge=0, description="UCs faturadas na última competência do período atual.")


class FatoresReceita(BaseModel):
    qtd_ucs_com_gd: int = Field(ge=0, description="UCs com GD conectada até a última competência do período atual.")
    energia_ucs_gd_base_kwh: float | None = Field(
        description="Volume, na referência, das UCs com GD no fim do período atual (A2). Nulo sem a A2 exportada."
    )
    energia_ucs_gd_atual_kwh: float | None = Field(description="Volume dessas mesmas UCs no período atual (A2).")
    qtd_trocas_medidor_atual: int = Field(ge=0)
    pct_faturas_bandeira_nao_verde_base: float | None
    pct_faturas_bandeira_nao_verde_atual: float | None


class VariacaoResponse(BaseModel):
    agrupar_por: Literal["municipio", "bairro", "classe"]
    periodo_base: Periodo
    periodo_atual: Periodo
    recorte: Literal["diagnostico", "personalizado"] = Field(
        description="diagnostico = períodos fixos da Gold (2022-07 a 2023-06 × 2025-07 a 2026-06)."
    )
    total: VariacaoLinha
    linhas: list[VariacaoLinha]
    fatores: FatoresReceita
    serie: list[SeriePonto] = Field(description="Valores mensais da seleção: referência e depois período atual.")


# ---------- unidades ----------
class CadastroUC(BaseModel):
    uc_id: str
    titular: str = Field(description="Nome de exibição; na Gold, usar nome_titular_mascarado.")
    classe: Literal["RESIDENCIAL", "RURAL", "COMERCIAL", "PODER PUBLICO", "INDUSTRIAL"]
    subgrupo_tarifario: Literal["B1", "B2", "B3", "A4"] | None = None
    classe_descricao: str
    municipio: str
    bairro: str
    alimentador_id: str
    status: str
    data_ligacao: date
    logradouro: str | None = None
    numero: str | None = None
    possui_gd: bool | None = None


class ConsumoMensalUC(BaseModel):
    competencia: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    consumo_kwh: float
    consumo_kwh_ano_anterior: float | None
    variacao_consumo_ano_anterior_pct: float | None = None
    valor_total: float | None = None
    valor_total_ano_anterior: float | None = None
    troca_medidor: bool | None = None
    troca_medidor_ano_anterior: bool | None = None


ClassificacaoVariacao = Literal["pequena", "moderada", "significativa", "reducao"]


class ComparacaoMetricaUC(BaseModel):
    valor_atual: float | None
    valor_referencia: float | None
    variacao_pct: float | None
    classificacao: ClassificacaoVariacao | None
    mensagem: str


class DiagnosticoContaAltaUC(BaseModel):
    competencias_disponiveis: list[Competencia]
    competencia_atual: Competencia | None
    competencia_referencia: Competencia | None
    troca_medidor_atual: bool | None
    troca_medidor_referencia: bool | None
    consumo: ComparacaoMetricaUC
    faturamento: ComparacaoMetricaUC
    mensagem: str


FaixaAtraso = Literal["EM DIA", "ATE 30 DIAS", "31 A 90 DIAS", "MAIS DE 90 DIAS"]
AbaFaturas = Literal["recentes", "historico"]
SituacaoFaturas = Literal["todas", "paga", "em_aberto"]


class FaturaUC(BaseModel):
    uc_id: str
    competencia: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    municipio: str
    bairro: str
    classe: str
    alimentador_id: str
    consumo_kwh: float
    valor: float = Field(description="Alias de valor_energia mantido para os serviços de receita e dashboard.")
    bandeira: str
    vencimento: date
    status: Literal["paga", "aberta", "atrasada"]
    faixa_atraso: FaixaAtraso
    id_fatura: str | None = None
    data_pagamento: date | None = None
    valor_energia: float | None = None
    valor_total: float | None = None
    tributos: float | None = None
    preco_medio_kwh: float | None = Field(
        default=None, description="Valor da energia / consumo em kWh; inclui bandeira e exclui tributos.",
    )


class ResumoFaturasUC(BaseModel):
    pendencias_recentes: int = Field(ge=0)
    pendencias_antigas: int = Field(ge=0)


class PaginaFaturasUC(BaseModel):
    itens: list[FaturaUC]
    total: int = Field(ge=0)
    pagina: int = Field(ge=1)
    tamanho: Literal[10] = 10
    anos_disponiveis: list[int]
    resumo: ResumoFaturasUC


class MedidorUC(BaseModel):
    medidor_id: str
    tipo: str
    data_instalacao: date
    status: str


class TrocaMedidorUC(BaseModel):
    id_uc: str
    mes_troca: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    id_medidor_antigo: str
    tipo_medidor_antigo: Literal["ELETRONICO", "ELETROMECANICO", "SMART"]
    idade_medidor_antigo_anos: float | None = Field(ge=0)
    id_medidor_novo: str
    tipo_medidor_novo: Literal["ELETRONICO", "ELETROMECANICO", "SMART"]
    consumo_medio_6m_antes: float | None = Field(ge=0)
    consumo_medio_6m_depois: float | None = Field(ge=0)
    variacao_consumo_pct: float | None
    classe: str
    municipio: str
    bairro: str


class GeracaoDistribuidaUC(BaseModel):
    potencia_kwp: float
    data_conexao: str = Field(description="Data de conexão no formato YYYY-MM-DD.")
    modalidade: str | None = Field(default=None, description="Modalidade de geração distribuída (dim_uc.modalidade_gd).")


TipoInterrupcao = Literal["FALTA DE ENERGIA", "DANO EM EQUIPAMENTO", "OSCILACAO", "SOBRECARGA", "FIO PARTIDO"]
CausaInterrupcao = Literal["CLIMATICA", "SOBRECARGA", "NAO IDENTIFICADA", "VEGETACAO", "TERCEIROS", "FALHA DE EQUIPAMENTO"]


class OcorrenciaRedeUC(BaseModel):
    ocorrencia_id: str
    alimentador_id: str
    municipio: str
    bairro: str
    classe: str
    tipo: TipoInterrupcao
    data: datetime
    competencia: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    duracao_min: int = Field(ge=0)
    causa: CausaInterrupcao | None
    causa_evitavel: bool
    uc_id: str
    data_fim: datetime


PeriodoHistorico = Literal["6_meses", "12_meses", "todos"]
PERIODO_HISTORICO_PADRAO: PeriodoHistorico = "12_meses"


class PeriodoHistoricoUC(BaseModel):
    periodo: PeriodoHistorico
    periodo_inicio: Competencia | None
    periodo_fim: Competencia | None


class InterrupcoesUC(PeriodoHistoricoUC):
    alimentador_id: str
    qtd_ocorrencias: int = Field(ge=0)
    duracao_total_min: int = Field(ge=0, description="Duração total das interrupções da própria UC no período.")
    dec_horas: float | None = Field(description="DEC do alimentador, como contexto da UC.")
    fec_vezes: float | None = Field(description="FEC do alimentador, como contexto da UC.")
    qtd_ucs_alimentador_mes: int | None = Field(ge=0, description="UCs do alimentador na competência de referência.")
    competencia_base_ucs: Competencia | None
    horas_interrompidas: float | None = Field(ge=0, description="Impacto acumulado do alimentador em UC × horas.")
    historico: list[OcorrenciaRedeUC]
    escopo: Literal["uc"] = Field(
        description="Escopo da contagem, duração total e histórico: a própria UC.",
    )


CanalAtendimento = Literal["TELEFONE", "APP", "WHATSAPP", "SITE", "PRESENCIAL"]
AssuntoAtendimento = Literal["FALTA DE ENERGIA", "FATURA", "DANO ELETRICO", "LIGACAO NOVA", "GERACAO DISTRIBUIDA", "RELIGACAO"]
SubassuntoAtendimento = Literal[
    "VISTORIA", "INTERRUPCAO PARCIAL", "INTERRUPCAO TOTAL", "OSCILACAO", "URGENCIA",
    "RESSARCIMENTO", "APOS PAGAMENTO", "SOLICITACAO", "HOMOLOGACAO", "PRAZO", "CREDITOS",
    "CONTESTACAO", "SEGUNDA VIA", "VALOR ALTO", "PARCELAMENTO",
]
AcaoAtendimento = Literal["ABERTURA", "ANALISE", "DESPACHO", "RETORNO AO CLIENTE", "ENCERRAMENTO"]


class AtendimentoUC(BaseModel):
    protocolo: str = Field(pattern=r"^AT\d{9}$")
    uc_id: str
    data: datetime
    data_fechamento: datetime | None
    canal: CanalAtendimento
    assunto: AssuntoAtendimento
    subassunto: SubassuntoAtendimento
    aberto: bool = Field(description="Situação do chamado; ultima_acao não determina se está aberto.")
    tempo_resolucao_horas: float | None = Field(ge=0)
    qtd_tratativas: int = Field(ge=1, le=3)
    ultima_acao: AcaoAtendimento
    nota_satisfacao: float | None = Field(ge=1, le=5, multiple_of=0.1)


class Visao360(BaseModel):
    cadastro: CadastroUC
    consumo: list[ConsumoMensalUC]
    diagnostico_conta_alta: DiagnosticoContaAltaUC
    faturas: list[FaturaUC]
    resumo_faturas: ResumoFaturasUC
    medidor: MedidorUC | None
    trocas_medidor: list[TrocaMedidorUC]
    geracao_distribuida: GeracaoDistribuidaUC | None
    interrupcoes: InterrupcoesUC
    periodo_atendimentos: PeriodoHistoricoUC
    atendimentos: list[AtendimentoUC]


# ---------- perdas ----------
class SuspeitaFila(BaseModel):
    posicao: int
    uc_id: str
    titular: str
    municipio: str
    bairro: str
    classe: str
    motivos: list[str]
    probabilidade: float
    energia_recuperavel_kwh_mes: float
    prioridade_score: float


TipoIrregularidade = Literal["fraude", "ligacao_clandestina", "erro_leitura", "erro_cadastro", "nenhuma"]


class OrdemCreate(BaseModel):
    uc_id: str
    motivo: str | None = None
    observacoes: str | None = None


class ResultadoInspecao(BaseModel):
    tipo: TipoIrregularidade
    energia_recuperada_kwh: float = Field(0, ge=0)
    observacoes: str | None = None


class Ordem(BaseModel):
    id: int
    uc_id: str
    status: Literal["PENDENTE", "EM_CAMPO", "CONCLUIDA", "CANCELADA"]
    motivo: str | None
    observacoes: str | None
    criada_em: str
    atualizada_em: str
    resultado: dict | None


class RejeicaoImportacao(BaseModel):
    linha: int = Field(description="Linha do arquivo (o cabeçalho é a linha 1).")
    ordem_id: int | None = None
    erro: str


class ResumoImportacao(BaseModel):
    total: int = Field(description="Linhas preenchidas que foram avaliadas (aceitas + rejeitadas).")
    aceitas: int
    ignoradas: int = Field(description="Linhas do modelo ainda sem preenchimento.")
    rejeitadas: list[RejeicaoImportacao]


# ---------- continuidade ----------
class AlimentadorDecFec(BaseModel):
    alimentador_id: str
    municipio: str
    dec_horas: float
    fec_vezes: float
    n_ocorrencias: int
    horas_interrompidas: float
    qtd_ucs_alimentador_mes: int | None
    competencia_base_ucs: Competencia | None
    horas_causas_evitaveis: float = 0
    qtd_ucs_afetadas: int = Field(0, description="UCs distintas com ao menos uma interrupção no período.")
    posicao_pior: int


class IndicadoresContinuidade(BaseModel):
    """DEC/FEC de um conjunto de alimentadores no período: soma dos índices mensais ponderados pelas UCs."""
    dec_horas: float
    fec_vezes: float
    qtd_interrupcoes: int
    horas_interrompidas: float
    horas_causas_evitaveis: float
    qtd_ucs: int | None
    competencia_base_ucs: Competencia | None


class PontoContinuidade(BaseModel):
    competencia: Competencia
    dec_horas: float
    fec_vezes: float
    qtd_interrupcoes: int
    horas_interrompidas: float


class CausaContinuidade(BaseModel):
    causa: str | None = Field(description="Nula quando a origem não informa a causa.")
    causa_evitavel: bool
    qtd_interrupcoes: int
    horas: float
    pct_horas: float | None


class LocalInterrupcao(BaseModel):
    """Interrupções agregadas por local da UC. Sem DEC: o do alimentador não vale para o bairro (contrato A8)."""
    municipio: str
    bairro: str | None = Field(description="Preenchido no nível bairro; sempre junto do município.")
    qtd_interrupcoes: int
    horas: float
    pct_horas: float | None
    qtd_ucs_afetadas: int
    qtd_ucs: int = Field(description="UCs cadastradas no local (no recorte do alimentador, quando houver).")
    pct_ucs_afetadas: float | None


class ResumoContinuidade(BaseModel):
    periodo_atual: Periodo
    periodo_base: Periodo | None
    municipio: str | None
    alimentador_id: str | None
    qtd_alimentadores: int
    atual: IndicadoresContinuidade | None
    base: IndicadoresContinuidade | None
    serie: list[PontoContinuidade]
    serie_base: list[PontoContinuidade]
    causas: list[CausaContinuidade]
    nivel_locais: Literal["municipio", "bairro"]
    locais: list[LocalInterrupcao]


# ---------- IA ----------
MAX_RAW_QUESTION_LENGTH = 16_384


class PerguntaIn(BaseModel):
    # Teto técnico do texto bruto; conteúdo e limite funcional pertencem à C1.
    pergunta: str = Field(max_length=MAX_RAW_QUESTION_LENGTH)
    sessao_id: str | None = None


class RespostaOut(BaseModel):
    status: Literal["ok", "nao_sei", "nao_implementado"]
    resposta: str
    sql_executado: str | None = None
    fontes: list[str] = []
    visualizacao: dict | None = None


class Insight(BaseModel):
    tipo: Literal["destaque", "alerta", "informativo"]
    texto: str
    dados: dict
