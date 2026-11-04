"""Resolução conservadora de alterações explícitas, sem chamada ao modelo."""
import re
import unicodedata


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def delta(question):
    text = normalize(question).strip(" ?.! ")
    if re.fullmatch(r"(?:pode |poderia )?(?:exibir|exiba|exibe|mostrar|mostre|mostra|gerar|gere|gera|criar|crie|cria)(?: um)? grafico (?:disso|disto|desses dados)", text):
        return "visualization", None
    geographic_text = question.strip(" ?.! ")
    geographic_text = re.sub(r"^(?:na verdade[, ]+)?(?:quero |considere |mude para |altere para |agora quero )", "", geographic_text, flags=re.I)
    geographic_text = re.sub(r",?\s+(?:no mesmo per[ií]odo|mantendo o per[ií]odo)$", "", geographic_text, flags=re.I)
    geography = re.fullmatch(r"(?:e )?(?:agora |apenas |somente )?(?:no[s]?|na[s]?|o[s]?|a[s]?) ((?:bairro[s]?|municipio) .+)", geographic_text, re.I)
    if geography:
        return "geography", geography[1]
    period = re.fullmatch(r"(?:e |agora )?(?:nos |os )?ultimos (\d{1,2}) meses(?: disponiveis)?", text)
    if period and 1 <= int(period[1]) <= 48:
        return "period", period[1]
    metric = re.fullmatch(r"(?:e |agora )?(?:considere |considerando |use )?(?:o |a )?(dec|fec)", text)
    if metric:
        return "metric", metric[1].upper()
    return None


def resolve_followup(question, memory_context):
    change = delta(question)
    if not change or not memory_context:
        return question
    entries = re.findall(r"(?:Estado: (\w+)\n)?Usuário: ([^\n]+)\nAssistente:", memory_context)
    if change[0] == "visualization" and (not entries or entries[-1][0] not in ("", "answered")):
        return question
    anchor = None
    for status, previous in entries:
        modification = delta(previous)
        if modification and anchor:
            anchor = apply_delta(anchor, modification)
        elif not modification and (status in ("", "answered") or change[0] == "geography"):
            anchor = previous
        elif not modification:
            anchor = None  # Mudança de assunto não confirmada: não herdar outra intenção.
    return (apply_delta(anchor, change) or question) if anchor else question


def apply_delta(anchor, change):
    kind, value = change
    if kind == "visualization":
        return anchor
    if kind == "geography":
        # Só troca um recorte explicitamente delimitado, preservando período e métrica.
        pattern = r"\b(?:em|no|na|nos|nas) (?:o |a )?(?:município de |municipio de |bairro[s]? )?.+?(?=\s+(?:entre|durante|nos últimos|nos ultimos|no período|no periodo)\b|[?]|$)"
        if not re.search(pattern, anchor, re.I):
            return None
        return re.sub(pattern, lambda m: "nos " + value if value.lower().startswith("bairros ") else "no " + value, anchor, count=1, flags=re.I)
    if kind == "period":
        if not re.search(r"[uú]ltimos \d{1,2} meses", anchor, flags=re.I):
            return None
        return re.sub(r"[uú]ltimos \d{1,2} meses", f"últimos {value} meses", anchor, flags=re.I)
    if len(set(re.findall(r"\b(?:DEC|FEC)\b", anchor, flags=re.I))) != 1:
        return None
    return re.sub(r"\b(?:DEC|FEC)\b", value, anchor, flags=re.I)


def financial_clarification(question, memory_context):
    if operational_expenses(question):
        return None
    if not re.search(r"\b(?:gastos?|despesas?)\b", normalize(question)):
        return None
    user_texts = [question] + re.findall(r"Usuário: ([^\n]+)", memory_context or "")
    definition = r"(?:gastos?|despesas?)\s+(?:significa[m]?|sao|e|como)\s+(?:o |os |as |a )?(?:valores? (?:das? )?)?(?:faturas?|faturamento|faturados?)\b"
    if any(re.search(definition, normalize(text)) for text in user_texts):
        return None
    return "Quando diz gastos ou despesas, você se refere ao valor das faturas de energia ou a despesas operacionais?"


def operational_expenses(question):
    return bool(re.search(r"\b(?:gastos?|despesas?) operacionais\b", normalize(question)))
