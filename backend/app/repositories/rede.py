"""Mapeamento da A7 da Gold para o histórico de interrupções da UC."""


def ocorrencia_publica(o: dict) -> dict:
    return {
        "ocorrencia_id": o["id_ocorrencia"], "uc_id": o["id_uc"],
        "alimentador_id": o["alimentador"], "municipio": o["municipio"],
        "bairro": o["bairro"], "classe": o["classe"], "tipo": o["tipo"],
        "data": o["data_hora_inicio"], "data_fim": o["data_hora_fim"],
        "competencia": o["mes_referencia"], "causa": o["causa"],
        "duracao_min": o["duracao_min"], "causa_evitavel": o["causa_evitavel"],
    }
