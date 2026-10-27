from __future__ import annotations

from app.mock.mock_data import CLASSES, MUNICIPIOS, build_mock_data
from app.repositories.base import OrdensStore
from app.repositories.ordens_store import MemoriaOrdensStore


class MockRepository:
    def __init__(self, ordens: OrdensStore | None = None) -> None:
        """`ordens`: onde guardar as ordens de inspeção. Sem ele, ficam só em memória (comportamento antigo)."""
        self.d = build_mock_data()
        self._ucs = {u["uc_id"]: u for u in self.d["ucs"]}
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
            f for f in self.d["faturas"]
            if inicio <= f["competencia"] <= fim
            and (municipio is None or f["municipio"] == municipio)
            and (bairro is None or f["bairro"] == bairro)
            and (classe is None or f["classe"] == classe)
        ]

    # UCs
    def buscar_ucs(self, q, municipio, classe, limite):
        q = (q or "").strip().lower()
        out = [
            u for u in self.d["ucs"]
            if (not q or q in u["uc_id"].lower() or q in u["titular"].lower())
            and (municipio is None or u["municipio"] == municipio)
            and (classe is None or u["classe"] == classe)
        ]
        return [self._publica(u) for u in out[:limite]]

    def uc(self, uc_id):
        u = self._ucs.get(uc_id.upper())
        return self._publica(u) if u else None

    @staticmethod
    def _publica(u):
        return {k: v for k, v in u.items() if not k.startswith("_")}

    def consumo_uc(self, uc_id):
        serie = self.d["consumo"].get(uc_id.upper(), [])
        return [{"competencia": c, "consumo_kwh": v} for c, v in zip(self.d["competencias"], serie, strict=True)]

    def faturas_uc(self, uc_id):
        return self.d["faturas_por_uc"].get(uc_id.upper(), [])

    def medidor_uc(self, uc_id):
        return self.d["medidores"].get(uc_id.upper())

    def gd_uc(self, uc_id):
        return self.d["gd"].get(uc_id.upper())

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
        return self._ordens.criar(dados)

    def listar_ordens(self, status=None):
        return self._ordens.listar(status)

    def obter_ordem(self, ordem_id):
        return self._ordens.obter(ordem_id)

    def atualizar_ordem(self, ordem_id, campos):
        return self._ordens.atualizar(ordem_id, campos)
