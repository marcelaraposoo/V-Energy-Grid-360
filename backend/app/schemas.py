from __future__ import annotations

from datetime import date
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


class DiagnosticoContaAltaUC(BaseModel):
    consumo_subiu: bool | None
    variacao_pct: float | None
    mensagem: str


class FaturaUC(BaseModel):
    uc_id: str
    competencia: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    municipio: str
    bairro: str
    classe: str
    alimentador_id: str
    consumo_kwh: float
    valor: float = Field(description="Valor legado do mock; não substitui valor_total ou valor_energia.")
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
    data_conexao: str = Field(description="Mock atual: YYYY-MM; adaptador Gold deverá fornecer YYYY-MM-DD.")
    fonte: str | None = None


class OcorrenciaRedeUC(BaseModel):
    ocorrencia_id: str
    alimentador_id: str
    municipio: str
    data: date
    competencia: Competencia = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    ucs_afetadas: int
    duracao_h: float
    causa: str
    uc_id: str | None = None
    data_fim: date | None = None


class InterrupcoesUC(BaseModel):
    alimentador_id: str
    ultimos_12_meses: int
    dec_horas: float | None
    fec_vezes: float | None
    recentes: list[OcorrenciaRedeUC]
    escopo: Literal["alimentador", "uc"] = Field(
        default="alimentador",
        description="O serviço atual consulta o alimentador; não são interrupções individuais da UC.",
    )


class TratativaAtendimentoUC(BaseModel):
    data: str = Field(description="O mock usa '—' quando a data da tratativa não está disponível.")
    descricao: str


class AtendimentoUC(BaseModel):
    protocolo: str
    data: date
    canal: str
    assunto: str
    status: str
    nota_satisfacao: float | None
    tratativas: list[TratativaAtendimentoUC]
    aberto: bool | None = None
    ultima_acao: str | None = None


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
