"""Gerador de dados MOCKADOS (determinístico) que imita o formato esperado da camada Gold.

Premissas do mock (ajustar quando a Gold real chegar):
- 48 competências (2022-10 a 2026-09), 400 UCs, 14 municípios, 2 alimentadores por município.
- Ocorrência de rede aqui é AGREGADA (ucs_afetadas + duracao_h); no dado real cada registro é 1 UC.
- Medidor sem 'última manutenção': na origem essa coluna é 100% vazia (docs/data_quality_log.md).
- Reajuste tarifário em degraus + bandeiras aleatórias, para o efeito-preço aparecer na decomposição.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

SEED = 42

MUNICIPIOS = {
    "Recife": ["Boa Viagem", "Casa Amarela", "Várzea", "Ibura", "Santo Amaro"],
    "Olinda": ["Rio Doce", "Varadouro", "Peixinhos", "Bairro Novo"],
    "Jaboatão dos Guararapes": ["Piedade", "Candeias", "Jardim Jordão", "Cavaleiro"],
    "Paulista": ["Janga", "Maranguape I", "Nobre"],
    "Camaragibe": ["Centro", "Timbi", "Tabatinga"],
    "São Lourenço da Mata": ["Centro", "Tiúma"],
    "Cabo de Santo Agostinho": ["Centro", "Charneca"],
    "Abreu e Lima": ["Centro", "Caetés"],
    "Igarassu": ["Centro", "Cruz de Rebouças"],
    "Ipojuca": ["Centro", "Nossa Senhora do Ó"],
    "Itapissuma": ["Centro", "Nova Itapissuma"],
    "Moreno": ["Centro", "Bonança"],
    "Araçoiaba": ["Centro", "Planalto"],
    "Ilha de Itamaracá": ["Pilar", "Forno da Cal"],
}
PESOS_MUN = [10, 6, 6, 4, 3, 2, 3, 2, 2, 2, 1, 1, 1, 1]

CLASSES = {"B1": "Residencial", "B2": "Rural", "B3": "Comercial/Poder público", "A4": "Industrial"}
CONSUMO_BASE = {"B1": 180, "B2": 220, "B3": 600, "A4": 8000}
TARIFA_KWH = {"B1": 0.85, "B2": 0.60, "B3": 0.80, "A4": 0.45}

BANDEIRAS = {"verde": 0.0, "amarela": 0.019, "vermelha1": 0.044, "vermelha2": 0.079}
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Hugo", "Iara", "João", "Karina", "Lucas", "Marina", "Nelson", "Olga", "Paulo"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Barbosa", "Ferreira", "Melo", "Albuquerque", "Cavalcanti"]
CAUSAS = ["Descarga atmosférica", "Árvore na rede", "Falha de equipamento", "Manutenção programada", "Sobrecarga", "Abalroamento de poste"]
ASSUNTOS = ["Conta alta", "Falta de luz", "Religação", "Segunda via", "Leitura incorreta", "Troca de medidor"]


def competencias() -> list[str]:
    out, y, m = [], 2022, 10
    for _ in range(48):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _prox_mes_dia10(comp: str) -> str:
    y, m = int(comp[:4]), int(comp[5:])
    m += 1
    if m == 13:
        y, m = y + 1, 1
    return f"{y}-{m:02d}-10"


@lru_cache(maxsize=1)
def build_mock_data() -> dict:
    rng = random.Random(SEED)
    comps = competencias()
    n = len(comps)

    # alimentadores
    alimentadores = []
    for mun in MUNICIPIOS:
        for _ in range(2):
            alimentadores.append({"id": f"AL{len(alimentadores) + 1:03d}", "municipio": mun, "ucs_total": 350})
    alim_por_mun: dict[str, list[str]] = {}
    for a in alimentadores:
        alim_por_mun.setdefault(a["municipio"], []).append(a["id"])
    piores = {"AL003", "AL011", "AL017"}

    # bandeira e fator tarifário por competência
    bandeira_comp = [rng.choices(list(BANDEIRAS), weights=[50, 25, 15, 10])[0] for _ in range(n)]
    fator_tarifa = [1.0 if i < 20 else 1.05 if i < 32 else 1.105 for i in range(n)]

    # unidades consumidoras
    muns = list(MUNICIPIOS)
    ucs, medidores, gd = [], {}, {}
    for i in range(400):
        mun = rng.choices(muns, weights=PESOS_MUN)[0]
        classe = rng.choices(list(CLASSES), weights=[75, 5, 15, 5])[0]
        uc_id = f"UC{i + 1:05d}"
        ucs.append({
            "uc_id": uc_id,
            "titular": f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}",
            "classe": classe,
            "classe_descricao": CLASSES[classe],
            "municipio": mun,
            "bairro": rng.choice(MUNICIPIOS[mun]),
            "alimentador_id": rng.choice(alim_por_mun[mun]),
            "status": rng.choices(["ativa", "suspensa"], weights=[96, 4])[0],
            "data_ligacao": f"{rng.randint(2005, 2022)}-{rng.randint(1, 12):02d}-01",
            "_base": CONSUMO_BASE[classe] * rng.uniform(0.6, 1.5),
            "_tend": rng.gauss(-0.01, 0.03),
        })
        medidores[uc_id] = {
            "medidor_id": f"MD{i + 1:06d}",
            "tipo": rng.choice(["Digital", "Inteligente", "Eletromecânico"]),
            "data_instalacao": f"{rng.randint(2012, 2024)}-{rng.randint(1, 12):02d}-15",
            "status": "ativo",
        }
        if rng.random() < 0.08:
            gd[uc_id] = {
                "potencia_kwp": round(rng.uniform(3, 10), 1),
                "data_conexao": comps[rng.randint(8, 30)],
                "fonte": "Solar fotovoltaica",
            }

    # consumo mensal
    queda_candidatas = [u for u in ucs if u["classe"] in ("B1", "B3") and u["uc_id"] not in gd]
    quedas = {u["uc_id"]: rng.randint(36, 44) for u in rng.sample(queda_candidatas, 25)}
    consumo: dict[str, list[float]] = {}
    for u in ucs:
        serie = []
        for i in range(n):
            v = u["_base"] * (1 + u["_tend"] * i / 12) * (1 + 0.12 * math.sin(2 * math.pi * i / 12)) * rng.gauss(1, 0.06)
            if u["uc_id"] in gd and comps[i] >= gd[u["uc_id"]]["data_conexao"]:
                v *= 0.6
            if u["uc_id"] in quedas and i >= quedas[u["uc_id"]]:
                v *= 0.45
            serie.append(round(max(v, 5), 1))
        consumo[u["uc_id"]] = serie

    # faturas
    faturas, faturas_por_uc = [], {}
    for u in ucs:
        for i, comp in enumerate(comps):
            kwh = consumo[u["uc_id"]][i]
            valor = round(kwh * (TARIFA_KWH[u["classe"]] * fator_tarifa[i] + BANDEIRAS[bandeira_comp[i]]), 2)
            if i >= n - 2:
                status = "aberta" if rng.random() < 0.45 else "paga"
            else:
                status = "atrasada" if rng.random() < 0.025 else "paga"
            f = {
                "uc_id": u["uc_id"], "competencia": comp, "municipio": u["municipio"], "bairro": u["bairro"],
                "classe": u["classe"], "alimentador_id": u["alimentador_id"], "consumo_kwh": kwh,
                "valor": valor, "bandeira": bandeira_comp[i], "vencimento": _prox_mes_dia10(comp), "status": status,
            }
            faturas.append(f)
            faturas_por_uc.setdefault(u["uc_id"], []).append(f)

    # ocorrências de rede (agregadas)
    ocorrencias = []
    for a in alimentadores:
        pesos = [20, 40, 30, 10] if a["id"] in piores else [60, 30, 8, 2]
        for comp in comps:
            for _ in range(rng.choices([0, 1, 2, 3], weights=pesos)[0]):
                ocorrencias.append({
                    "ocorrencia_id": f"OC{len(ocorrencias) + 1:06d}",
                    "alimentador_id": a["id"], "municipio": a["municipio"],
                    "data": f"{comp}-{rng.randint(1, 28):02d}", "competencia": comp,
                    "ucs_afetadas": rng.randint(40, 350),
                    "duracao_h": round(rng.lognormvariate(0.9 if a["id"] in piores else 0.4, 0.6), 2),
                    "causa": rng.choice(CAUSAS),
                })

    # atendimentos
    atendimentos: dict[str, list[dict]] = {}
    seq = 0
    for u in ucs:
        for _ in range(rng.choices([0, 1, 2, 3], weights=[50, 30, 15, 5])[0]):
            seq += 1
            atendimentos.setdefault(u["uc_id"], []).append({
                "protocolo": f"AT{seq:07d}",
                "data": f"{comps[rng.randint(30, 47)]}-{rng.randint(1, 28):02d}",
                "canal": rng.choice(["Telefone", "App", "WhatsApp", "Loja"]),
                "assunto": rng.choice(ASSUNTOS),
                "status": rng.choice(["Resolvido", "Resolvido", "Em andamento"]),
                "nota_satisfacao": rng.choice([None, 1, 2, 3, 4, 5]),
                "tratativas": [
                    {"data": "—", "descricao": "Chamado aberto"},
                    {"data": "—", "descricao": "Encaminhado à área responsável"},
                ],
            })

    # fila de suspeitas (perdas não técnicas)
    suspeitas = []
    for uc_id, i0 in quedas.items():
        antes = sum(consumo[uc_id][i0 - 12:i0]) / 12
        depois = sum(consumo[uc_id][i0:]) / (n - i0)
        suspeitas.append({
            "uc_id": uc_id,
            "motivos": ["Queda abrupta de consumo sem geração distribuída"],
            "probabilidade": round(rng.uniform(0.55, 0.9), 2),
            "energia_recuperavel_kwh_mes": round(antes - depois, 1),
        })
    outros = [u for u in ucs if u["uc_id"] not in quedas]
    for u in rng.sample(outros, 15):
        base = u["_base"]
        suspeitas.append({
            "uc_id": u["uc_id"],
            "motivos": [rng.choice(["Consumo muito abaixo do padrão da classe no bairro", "Medidor antigo (instalado há mais de 10 anos)", "Inspeção anterior com irregularidade"])],
            "probabilidade": round(rng.uniform(0.25, 0.6), 2),
            "energia_recuperavel_kwh_mes": round(base * rng.uniform(0.15, 0.4), 1),
        })

    return {
        "competencias": comps, "alimentadores": alimentadores, "ucs": ucs, "medidores": medidores,
        "gd": gd, "consumo": consumo, "faturas": faturas, "faturas_por_uc": faturas_por_uc,
        "ocorrencias": ocorrencias, "atendimentos": atendimentos, "suspeitas": suspeitas,
    }
