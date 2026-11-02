"""Mapeamento da B1 da Gold para o contrato público de atendimento da UC."""


def atendimento_publico(a: dict) -> dict:
    return {
        "protocolo": a["protocolo"], "uc_id": a["id_uc"],
        "data": a["data_hora_abertura"], "data_fechamento": a["data_hora_fechamento"],
        "canal": a["canal"], "assunto": a["assunto"], "subassunto": a["subassunto"],
        "aberto": a["aberto"], "tempo_resolucao_horas": a["tempo_resolucao_horas"],
        "qtd_tratativas": a["qtd_tratativas"], "ultima_acao": a["ultima_acao"],
        "nota_satisfacao": a["nota_satisfacao"],
    }
