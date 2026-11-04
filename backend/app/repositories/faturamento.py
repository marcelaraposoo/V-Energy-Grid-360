"""Mapeamento da fato de faturamento da Gold para o contrato público da UC."""

FAIXAS_RECENTES = ("EM DIA", "ATE 30 DIAS", "31 A 90 DIAS")
FAIXA_ANTIGA = "MAIS DE 90 DIAS"
TAMANHO_PAGINA = 6


def consumo_publico(faturas: list[dict]) -> list[dict]:
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
            "troca_medidor": f["troca_medidor"],
            "troca_medidor_ano_anterior": anterior["troca_medidor"] if anterior else None,
        })
    return serie


def fatura_publica(f: dict, uc: dict) -> dict:
    status = "paga" if f["status_fatura"] == "PAGA" else "atrasada" if f["dias_atraso"] > 0 else "aberta"
    return {
        "uc_id": f["id_uc"], "competencia": f["mes_referencia"],
        "municipio": f["municipio"], "bairro": f["bairro"],
        "classe": f["classe"], "alimentador_id": uc["alimentador"],
        "consumo_kwh": f["consumo_kwh"], "valor": f["valor_energia"],
        "bandeira": f["bandeira_tarifaria"], "vencimento": f["data_vencimento"],
        "status": status, "faixa_atraso": f["faixa_atraso"], "id_fatura": f["id_fatura"],
        "data_pagamento": f["data_pagamento"], "valor_energia": f["valor_energia"],
        "valor_total": f["valor_total"], "tributos": f["tributos"],
        "preco_medio_kwh": f["preco_medio_kwh"],
    }
