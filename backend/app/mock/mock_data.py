"""Gerador de dados MOCKADOS (determinístico).

Cadastro e consumo/faturas seguem dim_uc e fato_consumo_faturamento da Gold v2.
Premissas da simulação:
- 48 competências (2022-07 a 2026-06), 400 UCs, 14 municípios, 2 alimentadores por município.
- Nomes mascarados, endereços e coordenadas fictícios. Toda UC possui um medidor ativo.
- Tributos de 20% sobre valor_energia: regra fictícia, sem representar alíquotas reais.
- Ocorrência de rede aqui é AGREGADA (ucs_afetadas + duracao_h); no dado real cada registro é 1 UC.
- Medidor sem 'última manutenção': na origem essa coluna é 100% vazia (docs/data_quality_log.md).
- Reajuste tarifário em degraus + bandeiras aleatórias, para o efeito-preço aparecer na decomposição.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache

SEED = 42
DATA_REFERENCIA = date(2026, 6, 30)
ALIQUOTA_TRIBUTOS_MOCK = Decimal("0.20")

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
CLASSES_GOLD = {"B1": ("RESIDENCIAL",), "B2": ("RURAL",), "B3": ("COMERCIAL", "PODER PUBLICO"), "A4": ("INDUSTRIAL",)}
MODELOS_MEDIDOR = {"ELETRONICO": "EL-3000", "ELETROMECANICO": "EM-1000", "SMART": "SM-5000"}
MODALIDADES_GD = ("GERACAO NA PROPRIA UC", "AUTOCONSUMO REMOTO", "GERACAO COMPARTILHADA")

BANDEIRAS = {"verde": 0.0, "amarela": 0.019, "vermelha1": 0.044, "vermelha2": 0.079}
NOMES_BANDEIRAS = {"verde": "Verde", "amarela": "Amarela", "vermelha1": "Vermelha P1", "vermelha2": "Vermelha P2"}
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe", "Gabriela", "Hugo", "Iara", "João", "Karina", "Lucas", "Marina", "Nelson", "Olga", "Paulo"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Barbosa", "Ferreira", "Melo", "Albuquerque", "Cavalcanti"]
CAUSAS = ["Descarga atmosférica", "Árvore na rede", "Falha de equipamento", "Manutenção programada", "Sobrecarga", "Abalroamento de poste"]
ASSUNTOS = ["Conta alta", "Falta de luz", "Religação", "Segunda via", "Leitura incorreta", "Troca de medidor"]


def competencias() -> list[str]:
    out, y, m = [], 2022, 7
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
        uc_id = f"UC{i + 1:06d}"
        ano_ligacao = rng.randint(2005, 2022)
        mes_ligacao = rng.randint(1, 6 if ano_ligacao == 2022 else 12)
        ucs.append({
            "uc_id": uc_id,
            "titular": f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}",
            "classe": classe,
            "classe_descricao": CLASSES[classe],
            "municipio": mun,
            "bairro": rng.choice(MUNICIPIOS[mun]),
            "alimentador_id": rng.choice(alim_por_mun[mun]),
            "data_ligacao": f"{ano_ligacao}-{mes_ligacao:02d}-01",
            "_base": CONSUMO_BASE[classe] * rng.uniform(0.6, 1.5),
            "_tend": rng.gauss(-0.01, 0.03),
        })
        medidores[uc_id] = {
            "medidor_id": f"MD{i + 1:06d}",
            "tipo": rng.choice(list(MODELOS_MEDIDOR)),
            "data_instalacao": max(
                ucs[-1]["data_ligacao"],
                f"{rng.randint(2012, 2022)}-{rng.randint(1, 6):02d}-15",
            ),
            "status": "ativo",
        }
        if rng.random() < 0.08:
            gd[uc_id] = {
                "potencia_kwp": round(rng.uniform(3, 10), 1),
                "data_conexao": comps[rng.randint(8, 30)],
                "modalidade": MODALIDADES_GD[len(gd) % len(MODALIDADES_GD)],
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
            serie.append(round(max(v, 5)))
        consumo[u["uc_id"]] = serie

    # Contrato A1: uma linha por UC. Campos de simulação (_base e _tend) ficam fora da Gold.
    dim_uc = []
    for i, u in enumerate(ucs):
        uc_id = u["uc_id"]
        medidor = medidores[uc_id]
        geracao = gd.get(uc_id)
        classes = CLASSES_GOLD[u["classe"]]
        classe = classes[i % len(classes)]
        nomes = u["titular"].upper().split()
        media_atual = sum(consumo[uc_id][-12:]) / 12
        media_anterior = sum(consumo[uc_id][-24:-12]) / 12
        tipo_pessoa = "PJ" if classe in ("COMERCIAL", "PODER PUBLICO", "INDUSTRIAL") else "PF"
        dim_uc.append({
            "id_uc": uc_id,
            "nome_titular_mascarado": " ".join([nomes[0], *(f"{nome[0]}***" for nome in nomes[1:])]),
            "documento_mascarado": f"***.{i + 1:03d}.{i + 100:03d}-**" if tipo_pessoa == "PF" else f"**.***.{i + 1:03d}/0001-**",
            "tipo_pessoa": tipo_pessoa,
            "logradouro": f"Rua de Teste {i + 1}",
            "numero": str((i + 1) * 10),
            "bairro": u["bairro"],
            "municipio": u["municipio"],
            "uf": "PE",
            "cep": f"{50000000 + i:08d}",
            "latitude": round(-8.0 - (i % 30) / 1000, 6),
            "longitude": round(-34.9 - (i % 20) / 1000, 6),
            "classe": classe,
            "subgrupo_tarifario": u["classe"],
            "alimentador": u["alimentador_id"],
            "data_ligacao": u["data_ligacao"],
            "data_ligacao_estimada": False,
            "status": "ATIVA",
            "id_medidor_ativo": medidor["medidor_id"],
            "tipo_medidor_ativo": medidor["tipo"],
            "modelo_medidor_ativo": MODELOS_MEDIDOR[medidor["tipo"]],
            "data_instalacao_medidor": medidor["data_instalacao"],
            "idade_medidor_anos": round((DATA_REFERENCIA - date.fromisoformat(medidor["data_instalacao"])).days / 365.25, 2),
            "medidor_trocado_recentemente": False,
            "possui_gd": geracao is not None,
            "potencia_gd_kwp": geracao["potencia_kwp"] if geracao else None,
            "data_conexao_gd": f"{geracao['data_conexao']}-01" if geracao else None,
            "modalidade_gd": geracao["modalidade"] if geracao else None,
            "energia_injetada_media_kwh": round(CONSUMO_BASE[u["classe"]] * 0.4, 2) if geracao else None,
            "energia_injetada_atipica": False,
            "primeiro_mes_leitura": comps[0],
            "ultimo_mes_leitura": comps[-1],
            "consumo_medio_12m_kwh": round(media_atual, 2),
            "consumo_medio_12m_anterior_kwh": round(media_anterior, 2),
            "variacao_consumo_12m_pct": round((media_atual / media_anterior - 1) * 100, 2) if media_anterior else None,
        })

    # Contrato A2: uma leitura e uma fatura por UC e competência.
    fato_consumo_faturamento = []
    for u, cadastro in zip(ucs, dim_uc, strict=True):
        for i, comp in enumerate(comps):
            kwh = consumo[u["uc_id"]][i]
            tarifa = TARIFA_KWH[u["classe"]] * fator_tarifa[i] + BANDEIRAS[bandeira_comp[i]]
            energia = Decimal(str(kwh * tarifa)).quantize(Decimal("0.01"))
            tributos = (energia * ALIQUOTA_TRIBUTOS_MOCK).quantize(Decimal("0.01"))
            vencimento = date.fromisoformat(_prox_mes_dia10(comp))
            em_aberto = vencimento > DATA_REFERENCIA or rng.random() < 0.08
            pagamento = None if em_aberto else min(vencimento + timedelta(days=rng.choice([0, 0, 0, 5, 20, 45, 100])), DATA_REFERENCIA)
            atraso = max(0, ((pagamento or DATA_REFERENCIA) - vencimento).days)
            if atraso == 0:
                faixa_atraso = "EM DIA"
            elif atraso <= 30:
                faixa_atraso = "ATE 30 DIAS"
            elif atraso <= 90:
                faixa_atraso = "31 A 90 DIAS"
            else:
                faixa_atraso = "MAIS DE 90 DIAS"
            anterior = consumo[u["uc_id"]][i - 12] if i >= 12 else None
            ano, mes = map(int, comp.split("-"))
            fato_consumo_faturamento.append({
                "id_uc": u["uc_id"],
                "mes_referencia": comp,
                "ano": ano,
                "mes": mes,
                "periodo_diagnostico": "PRIMEIRO_ANO" if i < 12 else "ULTIMOS_12M" if i >= n - 12 else "OUTRO",
                "classe": cadastro["classe"],
                "bairro": cadastro["bairro"],
                "municipio": cadastro["municipio"],
                "possui_gd_no_mes": cadastro["possui_gd"] and comp >= cadastro["data_conexao_gd"][:7],
                "id_medidor": cadastro["id_medidor_ativo"],
                "data_leitura": f"{comp}-20",
                "tipo_leitura": "REAL",
                "consumo_kwh": kwh,
                "consumo_kwh_ano_anterior": anterior,
                "variacao_consumo_ano_anterior_pct": round((kwh / anterior - 1) * 100, 2) if anterior else None,
                "troca_medidor": False,
                "consumo_corrigido": False,
                "leitura_anterior_ausente": False,
                "id_fatura": f"FAT-{u['uc_id']}-{ano}{mes:02d}",
                "data_emissao": f"{comp}-25",
                "data_vencimento": vencimento.isoformat(),
                "data_pagamento": pagamento.isoformat() if pagamento else None,
                "valor_energia": float(energia),
                "tributos": float(tributos),
                "valor_total": float(energia + tributos),
                "bandeira_tarifaria": NOMES_BANDEIRAS[bandeira_comp[i]],
                "status_fatura": "EM ABERTO" if em_aberto else "PAGA",
                "em_aberto": em_aberto,
                "dias_atraso": atraso,
                "faixa_atraso": faixa_atraso,
                "preco_medio_kwh": round(float(energia) / kwh, 6),
            })

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
        "competencias": comps, "alimentadores": alimentadores,
        "dim_uc": dim_uc, "fato_consumo_faturamento": fato_consumo_faturamento,
        "ocorrencias": ocorrencias, "atendimentos": atendimentos, "suspeitas": suspeitas,
    }
