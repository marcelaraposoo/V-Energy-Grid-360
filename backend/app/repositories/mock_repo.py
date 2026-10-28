from __future__ import annotations

from app.mock.mock_data import CLASSES, MUNICIPIOS, build_mock_data
from app.repositories.base import OrdensStore
from app.repositories.ordens_store import MemoriaOrdensStore


class MockRepository:
    def __init__(self, ordens: OrdensStore | None = None) -> None:
        """`ordens`: onde guardar as ordens de inspeção. Sem ele, ficam só em memória (comportamento antigo)."""
        self.d = build_mock_data()
        self._ucs = {u["id_uc"]: u for u in self.d["dim_uc"]}
        self._faturas_por_uc: dict[str, list[dict]] = {}
        for fatura in self.d["fato_consumo_faturamento"]:
            self._faturas_por_uc.setdefault(fatura["id_uc"], []).append(fatura)
        self._ordens = ordens if ordens is not None else MemoriaOrdensStore()

    # catálogos
    def competencias(self):
        return self.d["competencias"]

    def municipios_bairros(self):
        return MUNICIPIOS

    def classes(self):
        return CLASSES

    def alimentadores(self, municipio=None):
        return [a for a in self.d["alimentadores"] if municipio is None or a["municipio"] == municipio]

    # faturamento
    def faturas(self, inicio, fim, municipio=None, bairro=None, classe=None):
        return [
            self._fatura(f) for f in self.d["fato_consumo_faturamento"]
            if inicio <= f["mes_referencia"] <= fim
            and (municipio is None or f["municipio"] == municipio)
            and (bairro is None or f["bairro"] == bairro)
            and (classe is None or self._ucs[f["id_uc"]]["subgrupo_tarifario"] == classe)
        ]

    # UCs
    def buscar_ucs(self, q, municipio, classe, limite):
        q = (q or "").strip().lower()
        out = [
            u for u in self._ucs.values()
            if (not q or q in u["id_uc"].lower() or q in u["nome_titular_mascarado"].lower())
            and (municipio is None or u["municipio"] == municipio)
            and (classe is None or u["subgrupo_tarifario"] == classe)
        ]
        return [self._cadastro(u) for u in out[:limite]]

    def uc(self, uc_id):
        u = self._ucs.get(uc_id.upper())
        return self._cadastro(u) if u else None

    @staticmethod
    def _cadastro(u):
        return {
            "uc_id": u["id_uc"], "titular": u["nome_titular_mascarado"],
            "classe": u["subgrupo_tarifario"],
            "classe_descricao": "Poder público" if u["classe"] == "PODER PUBLICO" else u["classe"].capitalize(),
            "municipio": u["municipio"], "bairro": u["bairro"],
            "alimentador_id": u["alimentador"], "status": u["status"],
            "data_ligacao": u["data_ligacao"], "logradouro": u["logradouro"],
            "numero": u["numero"], "possui_gd": u["possui_gd"],
        }

    def _fatura(self, f):
        uc = self._ucs[f["id_uc"]]
        status = "paga" if f["status_fatura"] == "PAGA" else "atrasada" if f["dias_atraso"] > 0 else "aberta"
        return {
            "uc_id": f["id_uc"], "competencia": f["mes_referencia"],
            "municipio": f["municipio"], "bairro": f["bairro"],
            "classe": uc["subgrupo_tarifario"], "alimentador_id": uc["alimentador"],
            "consumo_kwh": f["consumo_kwh"], "valor": f["valor_energia"],
            "bandeira": f["bandeira_tarifaria"], "vencimento": f["data_vencimento"],
            "status": status, "id_fatura": f["id_fatura"],
            "data_pagamento": f["data_pagamento"], "valor_energia": f["valor_energia"],
            "valor_total": f["valor_total"], "tributos": f["tributos"],
            "preco_medio_kwh": f["preco_medio_kwh"],
        }

    def consumo_uc(self, uc_id):
        faturas = self._faturas_por_uc.get(uc_id.upper(), [])
        por_competencia = {f["mes_referencia"]: f for f in faturas}
        serie = []
        for f in faturas:
            ano, mes = f["mes_referencia"].split("-")
            anterior = por_competencia.get(f"{int(ano) - 1}-{mes}")
            serie.append({
                "competencia": f["mes_referencia"], "consumo_kwh": f["consumo_kwh"],
                "consumo_kwh_ano_anterior": f["consumo_kwh_ano_anterior"],
                "variacao_consumo_ano_anterior_pct": f["variacao_consumo_ano_anterior_pct"],
                "valor_total": f["valor_total"],
                "valor_total_ano_anterior": anterior["valor_total"] if anterior else None,
            })
        return serie

    def faturas_uc(self, uc_id):
        return [self._fatura(f) for f in self._faturas_por_uc.get(uc_id.upper(), [])]

    def medidor_uc(self, uc_id):
        uc = self._ucs.get(uc_id.upper())
        if not uc:
            return None
        return {
            "medidor_id": uc["id_medidor_ativo"], "tipo": uc["tipo_medidor_ativo"],
            "data_instalacao": uc["data_instalacao_medidor"], "status": "ativo",
        }

    def gd_uc(self, uc_id):
        uc = self._ucs.get(uc_id.upper())
        if not uc or not uc["possui_gd"]:
            return None
        return {
            "potencia_kwp": uc["potencia_gd_kwp"], "data_conexao": uc["data_conexao_gd"],
            "modalidade": uc["modalidade_gd"],
        }

    def atendimentos_uc(self, uc_id):
        return [
            {
                "protocolo": a["protocolo"], "uc_id": a["id_uc"],
                "data": a["data_hora_abertura"], "data_fechamento": a["data_hora_fechamento"],
                "canal": a["canal"], "assunto": a["assunto"], "subassunto": a["subassunto"],
                "aberto": a["aberto"], "tempo_resolucao_horas": a["tempo_resolucao_horas"],
                "qtd_tratativas": a["qtd_tratativas"], "ultima_acao": a["ultima_acao"],
                "nota_satisfacao": a["nota_satisfacao"],
            }
            for a in self.d["fato_atendimento"] if a["id_uc"] == uc_id.upper()
        ]

    # rede
    @staticmethod
    def _ocorrencia(o):
        return {
            "ocorrencia_id": o["id_ocorrencia"], "uc_id": o["id_uc"],
            "alimentador_id": o["alimentador"], "municipio": o["municipio"],
            "bairro": o["bairro"], "classe": o["classe"], "tipo": o["tipo"],
            "data": o["data_hora_inicio"], "data_fim": o["data_hora_fim"],
            "competencia": o["mes_referencia"], "causa": o["causa"],
            "duracao_min": o["duracao_min"],
            "causa_evitavel": o["causa_evitavel"],
        }

    def ocorrencias(self, inicio, fim, alimentador_id=None, municipio=None, uc_id=None):
        return [
            self._ocorrencia(o) for o in self.d["fato_interrupcao"]
            if inicio <= o["mes_referencia"] <= fim
            and (alimentador_id is None or o["alimentador"] == alimentador_id)
            and (municipio is None or o["municipio"] == municipio)
            and (uc_id is None or o["id_uc"] == uc_id.upper())
        ]

    def indicadores_continuidade(self, inicio, fim, alimentador_id=None, municipio=None):
        return sorted([
            r for r in self.d["dec_fec_alimentador_mensal"]
            if inicio <= r["mes_referencia"] <= fim
            and (alimentador_id is None or r["alimentador"] == alimentador_id)
            and (municipio is None or r["municipio"] == municipio)
        ], key=lambda r: (r["mes_referencia"], r["alimentador"]))

    # perdas
    def suspeitas(self):
        return self.d["suspeitas"]

    def criar_ordem(self, dados):
        return self._ordens.criar(dados)

    def listar_ordens(self, status=None):
        return self._ordens.listar(status)

    def obter_ordem(self, ordem_id):
        return self._ordens.obter(ordem_id)

    def atualizar_ordem(self, ordem_id, campos):
        return self._ordens.atualizar(ordem_id, campos)
