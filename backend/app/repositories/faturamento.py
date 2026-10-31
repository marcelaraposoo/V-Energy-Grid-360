"""Mapeamento da fato de faturamento da Gold para o contrato público da UC."""

FAIXAS_RECENTES = ("EM DIA", "ATE 30 DIAS", "31 A 90 DIAS")
FAIXA_ANTIGA = "MAIS DE 90 DIAS"
TAMANHO_PAGINA = 10


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
