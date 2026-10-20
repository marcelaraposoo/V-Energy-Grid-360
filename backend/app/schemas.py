from __future__ import annotations

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
class Visao360(BaseModel):
    cadastro: dict
    consumo: list[dict]            # [{competencia, consumo_kwh, consumo_kwh_ano_anterior}]
    diagnostico_conta_alta: dict
    faturas: list[dict]
    faturas_em_aberto: list[dict]
    medidor: dict | None
    geracao_distribuida: dict | None
    interrupcoes: dict
    atendimentos: list[dict]


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
