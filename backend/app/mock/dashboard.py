"""Simulação das agregadas A3/A5 a partir das fatos fictícias do mock.

Não reproduz os totais oficiais do case. Dinheiro é somado com Decimal;
as razões da A5 seguem as casas decimais do notebook de KPIs da Gold.
"""
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP


def _soma(registros, coluna):
    return sum((Decimal(str(r[coluna])) for r in registros), Decimal(0))


def _razao(numerador, denominador, casas=2):
    if not denominador:
        return None
    valor = Decimal(str(numerador)) / Decimal(str(denominador))
    return float(valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP))


def _por_mes(registros):
    meses = defaultdict(list)
    for r in registros:
        meses[r["mes_referencia"]].append(r)
    return meses


def _resumo_faturas(faturas):
    abertas = [f for f in faturas if f["em_aberto"]]
    gd = [f for f in faturas if f["possui_gd_no_mes"]]
    return {
        "qtd_ucs_faturadas": len({f["id_uc"] for f in faturas}),
        "qtd_ucs_com_gd": len({f["id_uc"] for f in gd}),
        "consumo_kwh": float(_soma(faturas, "consumo_kwh")),
        "consumo_kwh_ucs_com_gd": float(_soma(gd, "consumo_kwh")),
        "receita_energia": float(_soma(faturas, "valor_energia")),
        "receita_total": float(_soma(faturas, "valor_total")),
        "qtd_faturas": len(faturas),
        "qtd_faturas_em_aberto": len(abertas),
        "valor_em_aberto": float(_soma(abertas, "valor_total")),
        "qtd_faturas_bandeira_nao_verde": sum(f["bandeira_tarifaria"] != "Verde" for f in faturas),
        "qtd_trocas_medidor": sum(f["troca_medidor"] for f in faturas),
    }


def build_fato_segmento_mensal(dim_uc, fato_consumo_faturamento, comps):
    """A3: somente segmentos existentes, inclusive cadastro ainda sem fatura."""
    cadastros = defaultdict(list)
    fatos = defaultdict(list)
    for uc in dim_uc:
        cadastros[uc["municipio"], uc["bairro"], uc["classe"]].append(uc)
    for f in fato_consumo_faturamento:
        fatos[f["mes_referencia"], (f["municipio"], f["bairro"], f["classe"])].append(f)
    linhas = []
    for comp in comps:
        for segmento, ucs in sorted(cadastros.items()):
            cadastradas = sum(u["data_ligacao"][:7] <= comp for u in ucs)
            faturas = fatos[comp, segmento]
            if not cadastradas and not faturas:
                continue
            municipio, bairro, classe = segmento
            linhas.append({
                "mes_referencia": comp, "municipio": municipio, "bairro": bairro, "classe": classe,
                "qtd_ucs_cadastradas": cadastradas, **_resumo_faturas(faturas),
            })
    return linhas


def build_kpis_mensal(dim_uc, fato_consumo_faturamento, fato_interrupcao, fato_atendimento, comps):
    """A5: uma linha por competência faturada; sem nota ou referência, mantém None."""
    faturamento = _por_mes(fato_consumo_faturamento)
    interrupcoes = _por_mes(fato_interrupcao)
    atendimentos = _por_mes(fato_atendimento)
    linhas = {}
    for comp in sorted(comps):
        faturas = faturamento[comp]
        if not faturas:
            continue
        resumo = _resumo_faturas(faturas)
        qtd_ucs = sum(u["data_ligacao"][:7] <= comp for u in dim_uc)
        bandeiras = Counter(f["bandeira_tarifaria"] for f in faturas)
        notas = [a for a in atendimentos[comp] if a["nota_satisfacao"] is not None]
        ano, mes = comp.split("-")
        anterior = linhas.get(f"{int(ano) - 1:04d}-{mes}")
        linhas[comp] = {
            "mes_referencia": comp, "qtd_ucs_cadastradas": qtd_ucs,
            "qtd_ucs_faturadas": resumo["qtd_ucs_faturadas"],
            "consumo_total_kwh": resumo["consumo_kwh"],
            "receita_energia": resumo["receita_energia"], "receita_total": resumo["receita_total"],
            "preco_medio_kwh": _razao(resumo["receita_energia"], resumo["consumo_kwh"], 4),
            "bandeira_predominante": min(bandeiras, key=lambda b: (-bandeiras[b], b)),
            "pct_faturas_bandeira_nao_verde": _razao(resumo["qtd_faturas_bandeira_nao_verde"] * 100, len(faturas)),
            "qtd_faturas_em_aberto": resumo["qtd_faturas_em_aberto"],
            "inadimplencia_pct": _razao(Decimal(str(resumo["valor_em_aberto"])) * 100, resumo["receita_total"]),
            "valor_em_aberto_mais_90_dias": float(_soma([
                f for f in faturas if f["em_aberto"] and f["faixa_atraso"] == "MAIS DE 90 DIAS"
            ], "valor_total")),
            "qtd_ucs_com_gd": resumo["qtd_ucs_com_gd"],
            "qtd_interrupcoes": len(interrupcoes[comp]),
            "dec_horas": _razao(_soma(interrupcoes[comp], "duracao_min"), qtd_ucs * 60, 4),
            "fec": _razao(len(interrupcoes[comp]), qtd_ucs, 4),
            "qtd_atendimentos": len(atendimentos[comp]),
            "nota_satisfacao_media": _razao(_soma(notas, "nota_satisfacao"), len(notas)),
            "variacao_consumo_ano_anterior_pct": _razao(
                (Decimal(str(resumo["consumo_kwh"])) - Decimal(str(anterior["consumo_total_kwh"]))) * 100,
                anterior["consumo_total_kwh"],
            ) if anterior else None,
            "variacao_receita_ano_anterior_pct": _razao(
                (Decimal(str(resumo["receita_energia"])) - Decimal(str(anterior["receita_energia"]))) * 100,
                anterior["receita_energia"],
            ) if anterior else None,
        }
    return list(linhas.values())
