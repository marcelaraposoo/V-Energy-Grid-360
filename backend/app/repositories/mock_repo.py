from __future__ import annotations

from app.mock.mock_data import MUNICIPIOS, build_mock_data
from app.repositories.atendimento import atendimento_publico
from app.repositories.base import OrdensStore
from app.repositories.faturamento import FAIXA_ANTIGA, FAIXAS_RECENTES, TAMANHO_PAGINA, consumo_publico, fatura_publica
from app.repositories.ordens_store import MemoriaOrdensStore
from app.repositories.rede import ocorrencia_publica


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
        cadastros = map(self._cadastro, self._ucs.values())
        return {u["classe"]: u["classe_descricao"] for u in cadastros}

    def alimentadores(self, municipio=None):
        return [a for a in self.d["alimentadores"] if municipio is None or a["municipio"] == municipio]

    # faturamento
    def faturas(self, inicio, fim, municipio=None, bairro=None, classe=None):
        return [
            self._fatura(f) for f in self.d["fato_consumo_faturamento"]
            if inicio <= f["mes_referencia"] <= fim
            and (municipio is None or f["municipio"] == municipio)
            and (bairro is None or f["bairro"] == bairro)
            and (classe is None or f["classe"] == classe)
        ]

    # UCs
    def buscar_ucs(self, q, municipio, classe, limite):
        q = (q or "").strip().lower()
        out = [
            u for u in self._ucs.values()
            if (not q or q in u["id_uc"].lower() or q in u["nome_titular_mascarado"].lower())
            and (municipio is None or u["municipio"] == municipio)
            and (classe is None or u["classe"] == classe)
        ]
        return [self._cadastro(u) for u in out[:limite]]

    def uc(self, uc_id):
        u = self._ucs.get(uc_id.upper())
        return self._cadastro(u) if u else None

    @staticmethod
    def _cadastro(u):
        return {
            "uc_id": u["id_uc"], "titular": u["nome_titular_mascarado"],
            "classe": u["classe"], "subgrupo_tarifario": u["subgrupo_tarifario"],
            "classe_descricao": "Poder público" if u["classe"] == "PODER PUBLICO" else u["classe"].capitalize(),
            "municipio": u["municipio"], "bairro": u["bairro"],
            "alimentador_id": u["alimentador"], "status": u["status"],
            "data_ligacao": u["data_ligacao"], "logradouro": u["logradouro"],
            "numero": u["numero"], "possui_gd": u["possui_gd"],
        }

    def _fatura(self, f):
        return fatura_publica(f, self._ucs[f["id_uc"]])

    def consumo_uc(self, uc_id):
        return consumo_publico(self._faturas_por_uc.get(uc_id.upper(), []))

    def faturas_uc(self, uc_id):
        return [self._fatura(f) for f in self._faturas_por_uc.get(uc_id.upper(), [])]

    def pagina_faturas_uc(self, uc_id, aba, ano, situacao, pagina):
        todas = self._faturas_por_uc.get(uc_id.upper(), [])
        abertas = [f for f in todas if f["status_fatura"] == "EM ABERTO"]
        resumo = {
            "pendencias_recentes": sum(f["faixa_atraso"] in FAIXAS_RECENTES for f in abertas),
            "pendencias_antigas": sum(f["faixa_atraso"] == FAIXA_ANTIGA for f in abertas),
        }
        competencias = set(sorted({f["mes_referencia"] for f in todas}, reverse=True)[:12])
        if aba == "recentes":
            filtradas = [f for f in todas if f["mes_referencia"] in competencias and (
                f["status_fatura"] == "PAGA" or f["faixa_atraso"] in FAIXAS_RECENTES
            )]
        else:
            filtradas = [f for f in todas
                         if (ano is None or f["mes_referencia"].startswith(f"{ano:04d}-"))
                         and (situacao == "todas" or f["status_fatura"] == (
                             "PAGA" if situacao == "paga" else "EM ABERTO"
                         ))]
        filtradas.sort(key=lambda f: (f["mes_referencia"], f["id_fatura"]), reverse=True)
        inicio = (pagina - 1) * TAMANHO_PAGINA
        return {
            "itens": [self._fatura(f) for f in filtradas[inicio:inicio + TAMANHO_PAGINA]],
            "total": len(filtradas), "pagina": pagina, "tamanho": TAMANHO_PAGINA,
            "anos_disponiveis": sorted({int(f["mes_referencia"][:4]) for f in todas}, reverse=True),
            "resumo": resumo,
        }

    def medidor_uc(self, uc_id):
        uc = self._ucs.get(uc_id.upper())
        if not uc:
            return None
        return {
            "medidor_id": uc["id_medidor_ativo"], "tipo": uc["tipo_medidor_ativo"],
            "data_instalacao": uc["data_instalacao_medidor"], "status": "ativo",
        }

    def trocas_medidor_uc(self, uc_id):
        return sorted(
            [t for t in self.d["fato_troca_medidor"] if t["id_uc"] == uc_id.strip().upper()],
            key=lambda t: t["mes_troca"], reverse=True,
        )

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
            atendimento_publico(a)
            for a in self.d["fato_atendimento"] if a["id_uc"] == uc_id.upper()
        ]

    # rede
    def ocorrencias(self, inicio, fim, alimentador_id=None, municipio=None, uc_id=None):
        return [
            ocorrencia_publica(o) for o in self.d["fato_interrupcao"]
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
