"""Detecta referências que exigem contexto; não bloqueia histórico disponível."""
import re

COMPLETE_QUESTION_MESSAGE = (
    "Para responder com segurança, envie a pergunta completa, incluindo a "
    "métrica, o período e os filtros desejados."
)


def requires_complete_question(question: str) -> bool:
    text = question.casefold().strip(" ?.!\n\t")
    if re.fullmatch(r"e (?:em|no|na) .+|(?:agora )?compara(?:r)? (?:os dois|com o ano passado)|qual foi o maior", text) and not re.search(
        r"\b(?:consumo|consumiu|faturamento|receita|interrupções|interrupcoes|atendimento|ucs|energia)\b", text
    ):
        return True
    if re.search(r"\b(?:disso|disto|desse|dessa|desses|dessas|nesse|nessa|nesses|nessas|naqueles|naquelas|dele|dela)\b|\bpara (?:ela|ele)\b", text):
        return True
    if re.search(r"\b(?:consulta|resposta|pergunta) anterior\b", text):
        return True
    if re.fullmatch(r"e (?:os|as) \d+ (?:meses|munic[íi]pios|bairros|alimentadores|ucs) com (?:mais|menos|maiores|menores) \w+", text):
        return True
    return bool(re.fullmatch(
        r"(?:(?:e|agora|considere|somente|apenas)\s+)*"
        r"(?:(?:o|a)\s+)?(?:dec|fec|top\s+\d+|"
        r"(?:nos?\s+|os?\s+)?[úu]ltimos\s+\d+\s+meses(?:\s+dispon[íi]veis)?|"
        r"(?:no|na|nos|nas)\s+(?:m[êe]s anterior|per[íi]odo anterior|mesmo per[íi]odo|"
        r"munic[íi]pio\s+.+|bairros?\s+.+))", text
    ))
