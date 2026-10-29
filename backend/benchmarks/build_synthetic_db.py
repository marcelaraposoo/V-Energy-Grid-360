import argparse
import math
import random
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


SEED = 42
DEFAULT_UCS = 1200
CUTOFF = date(2026, 7, 20)
N_MONTHS = 48
DB_PATH = Path(__file__).resolve().parent / "data" / "gold_synthetic.db"


# ---------------------------------------------------------------
# Esquema Gold v1 (colunas na ordem do contrato)
# ---------------------------------------------------------------

TABLES = {
    "dim_uc": [
        ("id_uc", "TEXT"), ("nome_titular_mascarado", "TEXT"),
        ("documento_mascarado", "TEXT"), ("tipo_pessoa", "TEXT"),
        ("logradouro", "TEXT"), ("numero", "TEXT"),
        ("bairro", "TEXT"), ("municipio", "TEXT"), ("uf", "TEXT"),
        ("cep", "TEXT"), ("latitude", "REAL"), ("longitude", "REAL"),
        ("classe", "TEXT"), ("subgrupo_tarifario", "TEXT"),
        ("alimentador", "TEXT"), ("data_ligacao", "TEXT"),
        ("data_ligacao_estimada", "INTEGER"), ("status", "TEXT"),
        ("id_medidor_ativo", "TEXT"), ("tipo_medidor_ativo", "TEXT"),
        ("modelo_medidor_ativo", "TEXT"),
        ("data_instalacao_medidor", "TEXT"),
        ("idade_medidor_anos", "REAL"),
        ("medidor_trocado_recentemente", "INTEGER"),
        ("possui_gd", "INTEGER"), ("potencia_gd_kwp", "REAL"),
        ("data_conexao_gd", "TEXT"), ("modalidade_gd", "TEXT"),
        ("energia_injetada_media_kwh", "REAL"),
        ("primeiro_mes_leitura", "TEXT"),
        ("ultimo_mes_leitura", "TEXT"),
    ],
    "fato_consumo_faturamento": [
        ("id_uc", "TEXT"), ("mes_referencia", "TEXT"),
        ("ano", "INTEGER"), ("mes", "INTEGER"),
        ("periodo_diagnostico", "TEXT"), ("classe", "TEXT"),
        ("bairro", "TEXT"), ("municipio", "TEXT"),
        ("id_medidor", "TEXT"), ("data_leitura", "TEXT"),
        ("tipo_leitura", "TEXT"), ("consumo_kwh", "INTEGER"),
        ("consumo_kwh_ano_anterior", "INTEGER"),
        ("variacao_consumo_ano_anterior_pct", "REAL"),
        ("troca_medidor", "INTEGER"), ("consumo_corrigido", "INTEGER"),
        ("leitura_anterior_ausente", "INTEGER"),
        ("id_fatura", "TEXT"), ("data_emissao", "TEXT"),
        ("data_vencimento", "TEXT"), ("data_pagamento", "TEXT"),
        ("valor_energia", "REAL"), ("tributos", "REAL"),
        ("valor_total", "REAL"), ("bandeira_tarifaria", "TEXT"),
        ("status_fatura", "TEXT"), ("em_aberto", "INTEGER"),
        ("dias_atraso", "INTEGER"), ("preco_medio_kwh", "REAL"),
    ],
    "receita_decomposicao": [
        ("municipio", "TEXT"), ("bairro", "TEXT"), ("classe", "TEXT"),
        ("qtd_ucs_periodo_0", "INTEGER"), ("qtd_ucs_periodo_1", "INTEGER"),
        ("volume_kwh_0", "REAL"), ("volume_kwh_1", "REAL"),
        ("receita_0", "REAL"), ("receita_1", "REAL"),
        ("preco_medio_0", "REAL"), ("preco_medio_1", "REAL"),
        ("variacao_receita", "REAL"), ("variacao_receita_pct", "REAL"),
        ("variacao_volume_pct", "REAL"),
        ("efeito_preco", "REAL"), ("efeito_volume", "REAL"),
        ("consumo_medio_uc_0", "REAL"), ("consumo_medio_uc_1", "REAL"),
        ("qtd_ucs_com_gd_1", "INTEGER"),
        ("qtd_trocas_medidor_1", "INTEGER"),
    ],
    "kpis_mensal": [
        ("mes_referencia", "TEXT"), ("qtd_ucs_faturadas", "INTEGER"),
        ("consumo_total_kwh", "REAL"), ("receita_energia", "REAL"),
        ("receita_total", "REAL"), ("preco_medio_kwh", "REAL"),
        ("bandeira_predominante", "TEXT"),
        ("qtd_faturas_em_aberto", "INTEGER"),
        ("inadimplencia_pct", "REAL"), ("qtd_ucs_com_gd", "INTEGER"),
        ("dec_horas", "REAL"), ("fec", "REAL"),
        ("qtd_atendimentos", "INTEGER"),
        ("nota_satisfacao_media", "REAL"),
        ("variacao_consumo_ano_anterior_pct", "REAL"),
        ("variacao_receita_ano_anterior_pct", "REAL"),
    ],
    "dec_fec_alimentador_mensal": [
        ("alimentador", "TEXT"), ("municipio", "TEXT"),
        ("mes_referencia", "TEXT"), ("qtd_ucs_alimentador", "INTEGER"),
        ("qtd_interrupcoes", "INTEGER"),
        ("horas_interrompidas", "REAL"), ("dec_horas", "REAL"),
        ("fec", "REAL"), ("causa_principal", "TEXT"),
        ("ranking_dec_mes", "INTEGER"),
    ],
    "fato_interrupcao": [
        ("id_ocorrencia", "TEXT"), ("id_uc", "TEXT"),
        ("alimentador", "TEXT"), ("bairro", "TEXT"),
        ("municipio", "TEXT"), ("tipo", "TEXT"), ("causa", "TEXT"),
        ("data_inicio", "TEXT"), ("data_fim", "TEXT"),
        ("mes_referencia", "TEXT"), ("duracao_min", "INTEGER"),
    ],
    "fato_atendimento": [
        ("protocolo", "TEXT"), ("id_uc", "TEXT"), ("canal", "TEXT"),
        ("assunto", "TEXT"), ("subassunto", "TEXT"),
        ("data_abertura", "TEXT"), ("data_fechamento", "TEXT"),
        ("mes_referencia", "TEXT"), ("aberto", "INTEGER"),
        ("tempo_resolucao_horas", "REAL"),
        ("qtd_tratativas", "INTEGER"), ("ultima_acao", "TEXT"),
        ("nota_satisfacao", "REAL"),
    ],
}


# ---------------------------------------------------------------
# Parâmetros do mundo sintético (nomes fictícios)
# ---------------------------------------------------------------

MUNICIPIOS = {
    "Recife": {"peso": 0.25, "alim": 4, "bairros": ["Boa Viagem", "Casa Amarela", "Varzea", "Centro", "Pina"]},
    "Jaboatao dos Guararapes": {"peso": 0.17, "alim": 3, "bairros": ["Piedade", "Candeias", "Jardim Jordao", "Centro", "Prazeres"]},
    "Olinda": {"peso": 0.10, "alim": 2, "bairros": ["Casa Caiada", "Bairro Novo", "Peixinhos", "Centro", "Rio Doce"]},
    "Paulista": {"peso": 0.09, "alim": 2, "bairros": ["Janga", "Maranguape", "Artur Lundgren", "Centro", "Nobre"]},
    "Camaragibe": {"peso": 0.06, "alim": 2, "bairros": ["Tabatinga", "Alberto Maia", "Centro", "Timbi", "Vila da Fabrica"]},
    "Cabo de Santo Agostinho": {"peso": 0.07, "alim": 2, "bairros": ["Centro", "Charneca", "Ponte dos Carvalhos", "Gaibu", "Pontezinha"]},
    "Abreu e Lima": {"peso": 0.05, "alim": 2, "bairros": ["Centro", "Caetes", "Timbo", "Fragoso", "Desterro"]},
    "Sao Lourenco da Mata": {"peso": 0.04, "alim": 1, "bairros": ["Centro", "Tiuma", "Pixete", "Matriz", "Nova Tiuma"]},
    "Igarassu": {"peso": 0.04, "alim": 1, "bairros": ["Centro", "Cruz de Reboucas", "Triunfo", "Nova Cruz", "Tres Ladeiras"]},
    "Moreno": {"peso": 0.03, "alim": 1, "bairros": ["Centro", "Alto do Cruzeiro", "Boa Vista", "Cabucu", "Vila Nova"]},
    "Ipojuca": {"peso": 0.04, "alim": 1, "bairros": ["Centro", "Camela", "Cupe", "Nossa Senhora do O", "Praia Azul"]},
    "Itapissuma": {"peso": 0.02, "alim": 1, "bairros": ["Centro", "Nova Itapissuma", "Botafogo", "Alto Bela Vista", "Santa Rita"]},
    "Ilha de Itamaraca": {"peso": 0.02, "alim": 1, "bairros": ["Centro", "Pilar", "Jaguaribe", "Forte Orange", "Baixa Verde"]},
    "Aracoiaba": {"peso": 0.02, "alim": 1, "bairros": ["Centro", "Tapera", "Amaro", "Cumbe", "Engenho Velho"]},
}

FEEDERS: dict[str, list[str]] = {}
_counter = 0

for _name, _info in MUNICIPIOS.items():
    FEEDERS[_name] = []

    for _ in range(_info["alim"]):
        _counter += 1
        FEEDERS[_name].append(f"ALIM-{_counter:02d}")

CLASSES = {
    "RESIDENCIAL": {"peso": 0.72, "sub": "B1", "base": 170, "tarifa": 0.78, "rate": -0.015},
    "COMERCIAL": {"peso": 0.15, "sub": "B3", "base": 650, "tarifa": 0.80, "rate": -0.005},
    "RURAL": {"peso": 0.04, "sub": "B2", "base": 230, "tarifa": 0.62, "rate": 0.0},
    "PODER PUBLICO": {"peso": 0.04, "sub": "B3", "base": 950, "tarifa": 0.80, "rate": -0.01},
    "INDUSTRIAL": {"peso": 0.05, "sub": "A4", "base": 3500, "tarifa": 0.45, "rate": 0.01},
}

GD_PROB = {"RESIDENCIAL": 0.08, "COMERCIAL": 0.10, "RURAL": 0.05}
GD_POWER = {"RESIDENCIAL": (2, 8), "COMERCIAL": (10, 60), "RURAL": (5, 30)}

DECLINE_EXTRA = -0.07
BANDEIRA_NAMES = ["VERDE", "AMARELA", "VERMELHA 1", "VERMELHA 2"]
BANDEIRA_WEIGHTS = [0.45, 0.30, 0.15, 0.10]
SURCHARGE = {"VERDE": 0.0, "AMARELA": 0.02, "VERMELHA 1": 0.045, "VERMELHA 2": 0.08}

CAUSAS = ["VEGETACAO", "DESCARGA ATMOSFERICA", "FALHA DE EQUIPAMENTO", "MANUTENCAO PROGRAMADA", "ACIDENTE VEICULAR", "SOBRECARGA"]
CAUSA_WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.08, 0.12]

CANAIS = ["TELEFONE", "APP", "WHATSAPP", "LOJA"]
SUBASSUNTOS = {
    "FALTA DE ENERGIA": ["SEM LUZ NA RUA", "SEM LUZ NA UC"],
    "CONTA ALTA": ["CONTESTACAO DE CONSUMO", "CONTESTACAO DE VALOR"],
    "SEGUNDA VIA": ["FATURA"],
    "RELIGACAO": ["APOS PAGAMENTO"],
    "MEDIDOR": ["DEFEITO", "TROCA"],
    "CADASTRO": ["ATUALIZACAO"],
}


# ---------------------------------------------------------------
# Utilidades de calendário
# ---------------------------------------------------------------

def month_label(index: int) -> str:
    total = 2022 * 12 + 6 + index

    return f"{total // 12}-{total % 12 + 1:02d}"


MONTHS = [month_label(i) for i in range(N_MONTHS)]


def month_start(label: str) -> date:
    return date(int(label[:4]), int(label[5:]), 1)


def month_end(label: str) -> date:
    start = month_start(label)
    following = date(
        start.year + start.month // 12,
        start.month % 12 + 1,
        1,
    )

    return following - timedelta(days=1)


def month_index(d: date) -> int:
    return max(0, (d.year - 2022) * 12 + d.month - 7)


def diagnostic_period(label: str) -> str:
    if "2022-07" <= label <= "2023-06":
        return "PRIMEIRO_ANO"

    if "2025-07" <= label <= "2026-06":
        return "ULTIMOS_12M"

    return "OUTRO"


def random_date(rng, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


# ---------------------------------------------------------------
# Geração
# ---------------------------------------------------------------

def build_ucs(rng, n_ucs: int) -> list[dict]:
    municipios = list(MUNICIPIOS)
    weights = [MUNICIPIOS[m]["peso"] for m in municipios]
    classes = list(CLASSES)
    class_weights = [CLASSES[c]["peso"] for c in classes]

    all_bairros = [
        (m, b) for m in MUNICIPIOS for b in MUNICIPIOS[m]["bairros"]
    ]
    declining = set(
        rng.sample(all_bairros, k=max(1, len(all_bairros) // 5))
    )

    ucs = []

    for n in range(1, n_ucs + 1):
        municipio = rng.choices(municipios, weights)[0]
        bairro = rng.choice(MUNICIPIOS[municipio]["bairros"])
        classe = rng.choices(classes, class_weights)[0]
        info = CLASSES[classe]

        if rng.random() < 0.80:
            ligacao = random_date(rng, date(2005, 1, 1), date(2022, 6, 30))
            estimada = rng.random() < 0.15
        else:
            ligacao = random_date(rng, date(2022, 7, 1), date(2026, 3, 31))
            estimada = False

        start_idx = month_index(ligacao)

        gd_date = None

        if (
            rng.random() < GD_PROB.get(classe, 0.0)
            and ligacao <= date(2025, 12, 31)
        ):
            gd_date = random_date(
                rng, max(ligacao, date(2023, 1, 1)), date(2025, 12, 31)
            )

        gd_idx = month_index(gd_date) if gd_date else None

        troca = rng.random() < 0.12 and ligacao <= date(2025, 12, 31)

        if troca:
            instalacao = random_date(
                rng,
                max(ligacao + timedelta(days=30), date(2023, 1, 1)),
                date(2026, 5, 31),
            )
        elif ligacao >= date(2022, 7, 1):
            instalacao = ligacao
        else:
            instalacao = random_date(rng, ligacao, date(2022, 6, 30))

        id_uc = f"UC{n:06d}"
        medidor = f"MED-{n:06d}"
        pj = (
            classe in ("COMERCIAL", "PODER PUBLICO", "INDUSTRIAL")
            and rng.random() < 0.9
        )

        if gd_date:
            potencia = round(rng.uniform(*GD_POWER[classe]), 1)
            injetada = round(potencia * rng.uniform(100, 130), 1)
            modalidade = rng.choice(
                ["AUTOCONSUMO LOCAL", "GERACAO COMPARTILHADA"]
            )
        else:
            potencia = injetada = modalidade = None

        dim_row = (
            id_uc,
            f"TITULAR {n:05d}***",
            (
                f"**.{rng.randint(100, 999)}.***/****-**"
                if pj
                else f"***.{rng.randint(100, 999)}.***-**"
            ),
            "PJ" if pj else "PF",
            f"Rua Sintetica {rng.randint(1, 400)}",
            str(rng.randint(1, 2500)),
            bairro,
            municipio,
            "PE",
            f"5{rng.randint(0, 9)}{rng.randint(100, 999)}-{rng.randint(100, 999)}",
            round(rng.uniform(-8.35, -7.75), 6),
            round(rng.uniform(-35.2, -34.8), 6),
            classe,
            info["sub"],
            None,  # alimentador: preenchido abaixo
            ligacao.isoformat(),
            int(estimada),
            "ATIVA" if rng.random() < 0.96 else "SUSPENSA",
            medidor,
            "ELETRONICO" if instalacao.year >= 2015 else "ELETROMECANICO",
            f"MOD-{rng.choice(['A100', 'B200', 'C300'])}",
            instalacao.isoformat(),
            round((date(2026, 6, 30) - instalacao).days / 365.25, 1),
            int(troca and instalacao >= date(2025, 7, 1)),
            int(gd_date is not None),
            potencia,
            gd_date.isoformat() if gd_date else None,
            modalidade,
            injetada,
            MONTHS[start_idx],
            "2026-06",
        )

        alimentador = rng.choice(FEEDERS[municipio])
        dim_row = dim_row[:14] + (alimentador,) + dim_row[15:]

        ucs.append(
            {
                "n": n,
                "id_uc": id_uc,
                "municipio": municipio,
                "bairro": bairro,
                "classe": classe,
                "alimentador": alimentador,
                "ligacao": ligacao,
                "start_idx": start_idx,
                "gd_idx": gd_idx,
                "gd_factor": rng.uniform(0.40, 0.65),
                "troca": troca,
                "inst_idx": month_index(instalacao),
                "medidor": medidor,
                "medidor_antigo": f"MED-{n:06d}-A" if troca else None,
                "base_factor": rng.lognormvariate(0, 0.35),
                "declining": (municipio, bairro) in declining,
                "dim_row": dim_row,
            }
        )

    return ucs


def build_interruptions(rng, ucs):
    feeder_ucs = defaultdict(list)

    for uc in ucs:
        feeder_ucs[uc["alimentador"]].append(uc)

    all_feeders = [f for fs in FEEDERS.values() for f in fs]
    feeder_mun = {f: m for m, fs in FEEDERS.items() for f in fs}
    bad_feeders = set(rng.sample(all_feeders, 4))

    rows = []
    hit = set()
    stats = defaultdict(
        lambda: {"count": 0, "minutes": 0, "causes": Counter()}
    )
    sequence = 0

    for feeder in all_feeders:
        bad = feeder in bad_feeders
        weights = (
            [0.10, 0.30, 0.35, 0.25] if bad else [0.35, 0.40, 0.18, 0.07]
        )

        for label in MONTHS:
            year, month = int(label[:4]), int(label[5:])

            for _ in range(rng.choices([0, 1, 2, 3], weights)[0]):
                start = datetime(
                    year, month, rng.randint(1, 28),
                    rng.randint(0, 23), rng.randint(0, 59),
                )
                causa = rng.choices(CAUSAS, CAUSA_WEIGHTS)[0]
                programada = causa == "MANUTENCAO PROGRAMADA"

                if programada:
                    base = rng.randint(120, 240)
                else:
                    base = rng.lognormvariate(math.log(90), 0.6) * (
                        1.6 if bad else 1.0
                    )

                eligible = [
                    u for u in feeder_ucs[feeder]
                    if u["ligacao"] <= start.date()
                ]

                if not eligible:
                    continue

                k = max(1, int(len(eligible) * rng.uniform(0.3, 0.8)))

                for uc in rng.sample(eligible, k):
                    minutes = max(5, int(base * rng.uniform(0.8, 1.2)))
                    sequence += 1
                    end = start + timedelta(minutes=minutes)

                    rows.append(
                        (
                            f"OC-{sequence:07d}",
                            uc["id_uc"],
                            feeder,
                            uc["bairro"],
                            uc["municipio"],
                            "PROGRAMADA" if programada else "NAO PROGRAMADA",
                            causa,
                            start.isoformat(sep=" "),
                            end.isoformat(sep=" "),
                            label,
                            minutes,
                        )
                    )
                    hit.add((uc["id_uc"], label))

                    entry = stats[(feeder, label)]
                    entry["count"] += 1
                    entry["minutes"] += minutes
                    entry["causes"][causa] += 1

    return rows, hit, stats, feeder_ucs, feeder_mun


def build_dec_fec(stats, feeder_ucs, feeder_mun):
    rows = []
    system = {}
    per_month = defaultdict(list)
    system_minutes = Counter()
    system_count = Counter()
    system_ucs = Counter()

    for feeder, municipio in feeder_mun.items():
        for label in MONTHS:
            end = month_end(label)
            qtd = sum(
                1 for u in feeder_ucs.get(feeder, []) if u["ligacao"] <= end
            )

            if qtd == 0:
                continue

            entry = stats.get((feeder, label))
            count = entry["count"] if entry else 0
            minutes = entry["minutes"] if entry else 0
            causa = (
                entry["causes"].most_common(1)[0][0]
                if entry and entry["causes"]
                else None
            )
            dec = round(minutes / 60 / qtd, 4)

            per_month[label].append(
                [
                    feeder, municipio, label, qtd, count,
                    round(minutes / 60, 2), dec,
                    round(count / qtd, 4), causa,
                ]
            )

            system_minutes[label] += minutes
            system_count[label] += count
            system_ucs[label] += qtd

    for label in MONTHS:
        items = sorted(per_month[label], key=lambda r: (-r[6], r[0]))

        for rank, item in enumerate(items, start=1):
            rows.append(tuple(item) + (rank,))

        total = system_ucs[label] or 1
        system[label] = (
            round(system_minutes[label] / 60 / total, 4),
            round(system_count[label] / total, 4),
        )

    return rows, system


def build_facts(rng, ucs, hit):
    bandeiras = rng.choices(BANDEIRA_NAMES, BANDEIRA_WEIGHTS, k=N_MONTHS)

    cons = {}
    fato_rows = []
    atend_rows = []
    kpi = defaultdict(
        lambda: {"n": 0, "cons": 0, "ve": 0.0, "vt": 0.0, "open": 0, "gd": 0}
    )
    att_count = Counter()
    att_notes = defaultdict(list)
    acc = defaultdict(
        lambda: {
            "vol": [0.0, 0.0], "rec": [0.0, 0.0],
            "ucs": [set(), set()], "months": [0, 0],
            "gd": set(), "trocas": 0,
        }
    )
    protocolo = 0

    for uc in ucs:
        info = CLASSES[uc["classe"]]
        base = info["base"] * uc["base_factor"]

        for i in range(uc["start_idx"], N_MONTHS):
            label = MONTHS[i]
            ano, mes = int(label[:4]), int(label[5:])

            trend = (1 + info["rate"]) ** (i / 12)

            if uc["declining"]:
                trend *= (1 + DECLINE_EXTRA) ** (i / 12)

            season = 1 + 0.08 * math.sin(2 * math.pi * (mes - 1) / 12)
            gd_active = uc["gd_idx"] is not None and i >= uc["gd_idx"]
            gd = uc["gd_factor"] if gd_active else 1.0

            consumo = max(
                1,
                round(base * trend * season * gd * rng.lognormvariate(0, 0.10)),
            )
            tipo = "REAL"

            if i > uc["start_idx"] and rng.random() < 0.04:
                tipo = "ESTIMADA"
                consumo = cons[(uc["n"], i - 1)]

            cons[(uc["n"], i)] = consumo

            prev = cons.get((uc["n"], i - 12)) if i >= 12 else None
            var = round((consumo - prev) / prev * 100, 2) if prev else None

            troca_mes = uc["troca"] and i == uc["inst_idx"]
            corrigido = bool(
                (troca_mes and rng.random() < 0.5) or rng.random() < 0.01
            )
            medidor = (
                uc["medidor_antigo"]
                if uc["troca"] and i < uc["inst_idx"]
                else uc["medidor"]
            )

            price = info["tarifa"] * (1 + 0.105 * i / 47) + SURCHARGE[
                bandeiras[i]
            ]
            ve = round(consumo * price, 2)
            tributos = round(ve * 0.25, 2)
            vt = round(ve + tributos, 2)

            emissao = month_end(label) + timedelta(days=5)
            vencimento = emissao + timedelta(days=10)
            paid_prob = (
                0.97 if label <= "2026-03"
                else 0.85 if label <= "2026-05"
                else 0.55
            )

            if rng.random() < paid_prob:
                pagamento = min(
                    vencimento + timedelta(days=rng.randint(-4, 12)),
                    CUTOFF,
                )
                status, aberto = "PAGA", 0
                atraso = max(0, (pagamento - vencimento).days)
                pago_str = pagamento.isoformat()
            else:
                status, aberto, pago_str = "EM ABERTO", 1, None
                atraso = max(0, (CUTOFF - vencimento).days)

            fato_rows.append(
                (
                    uc["id_uc"], label, ano, mes,
                    diagnostic_period(label), uc["classe"],
                    uc["bairro"], uc["municipio"], medidor,
                    (month_end(label) - timedelta(days=rng.randint(0, 4))).isoformat(),
                    tipo, consumo, prev, var,
                    int(troca_mes), int(corrigido), int(i == uc["start_idx"]),
                    f"FT-{uc['id_uc']}-{label}",
                    emissao.isoformat(), vencimento.isoformat(), pago_str,
                    ve, tributos, vt, bandeiras[i], status, aberto, atraso,
                    round(ve / consumo, 4),
                )
            )

            k = kpi[label]
            k["n"] += 1
            k["cons"] += consumo
            k["ve"] += ve
            k["vt"] += vt
            k["open"] += aberto
            k["gd"] += int(gd_active)

            period = diagnostic_period(label)

            if period != "OUTRO":
                p = 0 if period == "PRIMEIRO_ANO" else 1
                a = acc[(uc["municipio"], uc["bairro"], uc["classe"])]
                a["vol"][p] += consumo
                a["rec"][p] += ve
                a["ucs"][p].add(uc["id_uc"])
                a["months"][p] += 1

                if p == 1:
                    if gd_active:
                        a["gd"].add(uc["id_uc"])

                    if troca_mes:
                        a["trocas"] += 1

            assunto = None

            if (uc["id_uc"], label) in hit and rng.random() < 0.25:
                assunto = "FALTA DE ENERGIA"
            elif var is not None and var > 30 and rng.random() < 0.15:
                assunto = "CONTA ALTA"
            elif rng.random() < 0.015:
                assunto = rng.choice(
                    ["SEGUNDA VIA", "RELIGACAO", "MEDIDOR", "CADASTRO"]
                )

            if assunto:
                protocolo += 1
                abertura = month_start(label) + timedelta(days=rng.randint(0, 27))
                still_open = label >= "2026-05" and rng.random() < 0.2

                if still_open:
                    fechamento = horas = nota = None
                    ultima = "EM ANALISE"
                else:
                    horas = round(rng.lognormvariate(math.log(24), 0.8), 1)
                    fechamento = (
                        abertura + timedelta(days=int(horas // 24))
                    ).isoformat()
                    nota = (
                        float(rng.choice([1, 2, 3, 3, 4]))
                        if assunto == "FALTA DE ENERGIA"
                        else float(rng.randint(1, 5))
                    ) if rng.random() < 0.6 else None
                    ultima = "ENCERRADO"

                att_count[label] += 1

                if nota is not None:
                    att_notes[label].append(nota)

                atend_rows.append(
                    (
                        f"PR-{protocolo:07d}", uc["id_uc"],
                        rng.choice(CANAIS), assunto,
                        rng.choice(SUBASSUNTOS[assunto]),
                        abertura.isoformat(), fechamento, label,
                        int(still_open), horas, rng.randint(1, 5),
                        ultima, nota,
                    )
                )

    return fato_rows, atend_rows, kpi, att_count, att_notes, acc, bandeiras


def build_receita_decomposicao(acc):
    rows = []

    for (municipio, bairro, classe), a in sorted(acc.items()):
        v0, v1 = a["vol"]
        r0, r1 = a["rec"]

        if v0 <= 0 or v1 <= 0:
            continue

        p0, p1 = r0 / v0, r1 / v1

        rows.append(
            (
                municipio, bairro, classe,
                len(a["ucs"][0]), len(a["ucs"][1]),
                round(v0, 2), round(v1, 2),
                round(r0, 2), round(r1, 2),
                round(p0, 4), round(p1, 4),
                round(r1 - r0, 2), round((r1 - r0) / r0 * 100, 2),
                round((v1 - v0) / v0 * 100, 2),
                round((p1 - p0) * v1, 2), round((v1 - v0) * p0, 2),
                round(v0 / a["months"][0], 2), round(v1 / a["months"][1], 2),
                len(a["gd"]), a["trocas"],
            )
        )

    return rows


def build_kpis(kpi, att_count, att_notes, system, bandeiras):
    rows = []

    for i, label in enumerate(MONTHS):
        k = kpi[label]
        notes = att_notes[label]
        dec, fec = system.get(label, (None, None))

        yoy_cons = yoy_rec = None

        if i >= 12:
            before = kpi[MONTHS[i - 12]]

            if before["cons"]:
                yoy_cons = round((k["cons"] - before["cons"]) / before["cons"] * 100, 2)

            if before["vt"]:
                yoy_rec = round((k["vt"] - before["vt"]) / before["vt"] * 100, 2)

        rows.append(
            (
                label, k["n"], float(k["cons"]), round(k["ve"], 2),
                round(k["vt"], 2), round(k["ve"] / k["cons"], 4),
                bandeiras[i], k["open"], round(k["open"] / k["n"] * 100, 2),
                k["gd"], dec, fec, att_count[label],
                round(sum(notes) / len(notes), 2) if notes else None,
                yoy_cons, yoy_rec,
            )
        )

    return rows


# ---------------------------------------------------------------
# Banco e verificação
# ---------------------------------------------------------------

def create_tables(conn):
    for table, columns in TABLES.items():
        definition = ", ".join(f"{name} {kind}" for name, kind in columns)
        conn.execute(f"CREATE TABLE {table} ({definition})")


def insert(conn, table, rows):
    names = [name for name, _ in TABLES[table]]
    placeholders = ", ".join("?" for _ in names)

    conn.executemany(
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})",
        rows,
    )


def verify(conn):
    cur = conn.cursor()

    print("\nLinhas por tabela:")

    for table in TABLES:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")

    diff = cur.execute(
        "SELECT MAX(ABS(variacao_receita - (efeito_preco + efeito_volume))) "
        "FROM receita_decomposicao"
    ).fetchone()[0]
    shared = cur.execute(
        "SELECT COUNT(*) FROM (SELECT bairro FROM dim_uc GROUP BY bairro "
        "HAVING COUNT(DISTINCT municipio) > 1)"
    ).fetchone()[0]
    v0, v1, r0, r1 = cur.execute(
        "SELECT SUM(volume_kwh_0), SUM(volume_kwh_1), "
        "SUM(receita_0), SUM(receita_1) FROM receita_decomposicao"
    ).fetchone()

    print(f"\nMaior diferença efeitos x variação de receita: {diff:.4f} (esperado < 0.05)")
    print(f"Bairros com o mesmo nome em mais de um município: {shared} (esperado > 0)")
    print(
        f"Volume {(v1 - v0) / v0 * 100:+.1f}% | "
        f"Receita {(r1 - r0) / r0 * 100:+.1f}% "
        "(sintético, não calibrado com o caso real)"
    )

    orphans = cur.execute(
        "SELECT COUNT(*) FROM fato_consumo_faturamento f "
        "LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL"
    ).fetchone()[0]

    print(f"Fatos sem UC no cadastro: {orphans} (esperado 0)")


def main(n_ucs: int, seed: int, output: Path):
    rng = random.Random(seed)

    ucs = build_ucs(rng, n_ucs)
    interruptions, hit, stats, feeder_ucs, feeder_mun = build_interruptions(rng, ucs)
    dec_fec, system = build_dec_fec(stats, feeder_ucs, feeder_mun)
    fatos, atendimentos, kpi, att_count, att_notes, acc, bandeiras = build_facts(
        rng, ucs, hit
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    conn = sqlite3.connect(output)

    create_tables(conn)
    insert(conn, "dim_uc", [uc["dim_row"] for uc in ucs])
    insert(conn, "fato_consumo_faturamento", fatos)
    insert(conn, "receita_decomposicao", build_receita_decomposicao(acc))
    insert(conn, "kpis_mensal", build_kpis(kpi, att_count, att_notes, system, bandeiras))
    insert(conn, "dec_fec_alimentador_mensal", dec_fec)
    insert(conn, "fato_interrupcao", interruptions)
    insert(conn, "fato_atendimento", atendimentos)
    conn.commit()

    verify(conn)
    conn.close()

    print(f"\nBanco salvo em: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ucs", type=int, default=DEFAULT_UCS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=DB_PATH)

    arguments = parser.parse_args()

    main(arguments.ucs, arguments.seed, arguments.output)