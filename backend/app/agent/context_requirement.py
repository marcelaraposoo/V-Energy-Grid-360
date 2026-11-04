"""Orientação fixa para referências explícitas sem pergunta autossuficiente.

Não interpreta o histórico, não resolve localidades e não depende do tamanho da
frase. Formas não reconhecidas continuam sujeitas ao contrato da C4.1.
"""
import re

COMPLETE_QUESTION_MESSAGE = (
    "Para responder com segurança, envie a pergunta completa, incluindo a "
    "métrica, o período e os filtros desejados."
)


def requires_complete_question(question: str) -> bool:
    text = question.casefold().strip(" ?.!\n\t")
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
