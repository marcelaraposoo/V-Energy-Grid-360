from __future__ import annotations

from datetime import datetime

from app.mock.mock_data import CLASSES, MUNICIPIOS, build_mock_data


class MockRepository:
    def __init__(self) -> None:
        self.d = build_mock_data()
        self._ucs = {u["id_uc"]: u for u in self.d["dim_uc"]}
        self._faturas_por_uc: dict[str, list[dict]] = {}
        for fatura in self.d["fato_consumo_faturamento"]:
            self._faturas_por_uc.setdefault(fatura["id_uc"], []).append(fatura)
        self._ordens: dict[int, dict] = {}
        self._seq = 0

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
            "valor_total": f["valor_total"],
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
        return self.d["atendimentos"].get(uc_id.upper(), [])

    # rede
    def ocorrencias(self, inicio, fim, alimentador_id=None, municipio=None):
        return [
            o for o in self.d["ocorrencias"]
            if inicio <= o["competencia"] <= fim
            and (alimentador_id is None or o["alimentador_id"] == alimentador_id)
            and (municipio is None or o["municipio"] == municipio)
        ]

    # perdas
    def suspeitas(self):
        return self.d["suspeitas"]

    def criar_ordem(self, dados):
        self._seq += 1
        agora = datetime.now().isoformat(timespec="seconds")
        ordem = {"id": self._seq, "status": "PENDENTE", "criada_em": agora, "atualizada_em": agora,
                 "resultado": None, **dados}
        self._ordens[self._seq] = ordem
        return ordem

    def listar_ordens(self, status=None):
        return [o for o in self._ordens.values() if status is None or o["status"] == status]

    def obter_ordem(self, ordem_id):
        return self._ordens.get(ordem_id)

    def atualizar_ordem(self, ordem_id, campos):
        o = self._ordens[ordem_id]
        o.update(campos, atualizada_em=datetime.now().isoformat(timespec="seconds"))
        return o
