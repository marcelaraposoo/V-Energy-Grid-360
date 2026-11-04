"""Evidência do período no contrato de indicadores móveis, sem liberar medidas."""
import re
from sqlglot import parse_one, exp


def numeric_validation_text(text, sql, result):
    try:
        tree = parse_one(sql, read="sqlite")
        tables = list(tree.find_all(exp.Table))
        if (not isinstance(tree, exp.Select) or len(tables) != 1
            or tables[0].name != "dec_fec_alimentador_mensal"
            or len(list(tree.find_all(exp.Select))) != 1):
            return text
        for index, projection in enumerate(tree.expressions):
            value = projection.unalias()
            if isinstance(value, exp.Sum):
                value = value.this
            if (isinstance(value, exp.Column) and value.name in {"dec_12m_horas", "fec_12m"}
                and index < len(result.columns) and result.columns[index] == projection.alias_or_name):
                # Só o numeral do período conhecido é dispensado da comparação
                # com valores medidos. "12 horas", dinheiro e datas não mudam.
                return re.sub(r"(?<![\w.,])12(?=\s+meses\b)", "[período]", text, flags=re.I)
    except Exception:
        pass
    return text
