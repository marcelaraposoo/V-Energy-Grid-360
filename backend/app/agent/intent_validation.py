"""Contradições verificáveis entre pedido explícito e estrutura SQL; sem LLM."""
import re
from sqlglot import parse_one, exp
import unicodedata


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def needs_domain_recheck(question):
    """Veta uma recusa prematura; não aprova SQL nem substitui segurança."""
    text = normalize(question)
    analytical = re.search(r"\b(?:qual|quais|quanto|quantas|onde|compare|compara|mostre)\b", text)
    operational = re.search(r"\b(?:consumo|consumiu|faturamento|faturas|interrupcoes|atendimentos|conta de luz|falta de luz|energia gasta)\b", text)
    return bool(analytical and operational)


def sql_intent_problem(question, sql):
    try:
        tree = parse_one(sql, read="sqlite")
    except Exception:
        return None  # C4.2 valida sintaxe e segurança.
    text = normalize(question)
    columns = {c.name.lower() for c in tree.find_all(exp.Column)}
    period = re.search(r"ultimos (\d+) meses", text)
    if period and int(period[1]) != 12 and columns & {"dec_12m_horas", "fec_12m"}:
        return "A consulta proposta não corresponde à janela mensal solicitada. Reformule o período para uma nova tentativa."
    count = re.search(r"\btop\s+(\d+)\b|\b(?:os|as|quais|liste|de)\s+(\d+)\s+(?:alimentadores|municipios|bairros|meses)\b", text)
    if count:
        requested = int(count[1] or count[2])
        limit = tree.args.get("limit")
        if limit is not None and isinstance(limit.expression, exp.Literal):
            if limit.expression.is_int and int(limit.expression.this) != requested:
                return "A quantidade proposta não corresponde ao TOP solicitado. Confirme o recorte para uma nova consulta."
    total = bool(re.search(r"\b(?:valor(?:es)? faturado(?:s)?|faturamento total|total da fatura)\b", text))
    energy = bool(re.search(r"\b(?:sem tributos|receita de energia|valor da energia)\b", text))
    if total and not energy and columns & {"receita_energia", "valor_energia"} and not columns & {"receita_total", "valor_total"}:
        return "Faturamento total inclui tributos; a consulta proposta usa somente receita de energia. Especifique qual métrica deseja."
    if energy and columns & {"receita_total", "valor_total"} and not columns & {"receita_energia", "valor_energia"}:
        return "Receita de energia sem tributos não equivale ao total da fatura. A consulta proposta precisa ser corrigida."
    interrupted = affected_uc_count(question)
    if interrupted:
        tables = {t.name.lower() for t in tree.find_all(exp.Table)}
        counts = [p.unalias() for p in tree.expressions if isinstance(p.unalias(), exp.Count)] if isinstance(tree, exp.Select) else []
        distinct_uc = any(isinstance(c.this, exp.Distinct) and len(c.this.expressions) == 1
            and isinstance(c.this.expressions[0], exp.Column) and c.this.expressions[0].name.lower() == "id_uc" for c in counts)
        # Uma contagem de unidades distintas não é uma listagem UC-mês nem
        # uma soma de ocorrências. Planos complexos sem prova são recusados.
        if tables - {"fato_interrupcao", "dim_uc"} or "fato_interrupcao" not in tables or not distinct_uc or len(list(tree.find_all(exp.Select))) != 1:
            return "A quantidade de UCs afetadas exige contagem distinta de unidades em interrupções, não faturas, consumo ou quantidade de ocorrências."
        if tree.args.get("group") and not re.search(r"\bpor (?:bairro|municipio|classe|alimentador)", text):
            return "A quantidade total de unidades distintas não deve ser dividida em registros individuais."
        if any(isinstance(p.unalias(), exp.Column) and p.unalias().name.lower() not in {"municipio", "bairro", "classe", "alimentador"} for p in tree.expressions):
            return "Uma quantidade agregada de UCs afetadas não pode ser substituída por uma listagem individual."
    return None


def affected_uc_count(question):
    text = normalize(question)
    return bool(re.search(r"\b(?:quantas|quantidade|numero|total)\b", text)
        and re.search(r"\b(?:ucs?|unidades consumidoras)\b", text)
        and ("interrup" in text or "sem luz" in text or "sem energia" in text))
