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
class Kpi(BaseModel):
    nome: str
    unidade: str
    valor_atual: float
    valor_base: float
    variacao_abs: float
    variacao_pct: float | None


class KpisResponse(BaseModel):
    periodo_base: Periodo
    periodo_atual: Periodo
    kpis: list[Kpi]


class SeriePonto(BaseModel):
    competencia: Competencia
    receita: float
    energia_kwh: float
    tarifa_media: float


class VariacaoLinha(BaseModel):
    chave: str
    receita_base: float
    receita_atual: float
    variacao_receita: float
    efeito_preco: float
    efeito_volume: float
    energia_base_kwh: float
    energia_atual_kwh: float
    variacao_energia_pct: float | None


class VariacaoResponse(BaseModel):
    agrupar_por: Literal["municipio", "bairro", "classe"]
    periodo_base: Periodo
    periodo_atual: Periodo
    total: VariacaoLinha
    linhas: list[VariacaoLinha]


# ---------- unidades ----------
class CadastroUC(BaseModel):
    uc_id: str
    titular: str = Field(description="Nome de exibição; na Gold, usar nome_titular_mascarado.")
    classe: str = Field(description="Subgrupo tarifário no contrato atual, como B1 ou A4.")
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
    consumo: ComparacaoMetricaUC
    faturamento: ComparacaoMetricaUC
    mensagem: str


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
    id_fatura: str | None = None
    data_pagamento: date | None = None
    valor_energia: float | None = None
    valor_total: float | None = None


class MedidorUC(BaseModel):
    medidor_id: str
    tipo: str
    data_instalacao: date
    status: str


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


PeriodoInterrupcoes = Literal["6_meses", "12_meses", "todos"]
PERIODO_INTERRUPCOES_PADRAO: PeriodoInterrupcoes = "12_meses"


class InterrupcoesUC(BaseModel):
    alimentador_id: str
    periodo: PeriodoInterrupcoes
    qtd_ocorrencias: int = Field(ge=0)
    duracao_total_min: int = Field(ge=0, description="Duração total das interrupções da própria UC no período.")
    dec_horas: float | None = Field(description="DEC do alimentador, como contexto da UC.")
    fec_vezes: float | None = Field(description="FEC do alimentador, como contexto da UC.")
    periodo_inicio: Competencia | None
    periodo_fim: Competencia | None
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
    faturas_em_aberto: list[FaturaUC]
    medidor: MedidorUC | None
    geracao_distribuida: GeracaoDistribuidaUC | None
    interrupcoes: InterrupcoesUC
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
    posicao_pior: int


# ---------- IA ----------
class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500)
    sessao_id: str | None = None


class RespostaOut(BaseModel):
    status: Literal["ok", "nao_sei", "nao_implementado"]
    resposta: str
    sql_executado: str | None = None
    fontes: list[str] = []


class Insight(BaseModel):
    tipo: Literal["destaque", "alerta", "informativo"]
    texto: str
    dados: dict
