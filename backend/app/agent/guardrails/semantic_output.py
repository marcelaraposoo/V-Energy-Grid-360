"""Verifica afirmações explícitas quando o resultado oferece evidência inequívoca."""
import re
from app.agent.conversation import normalize
from app.agent.guardrails.output_rules import extract_dates, extract_numbers
from app.agent.guardrails.allowed_numbers import build_allowed_numbers, is_number_supported
from app.agent.schemas import QueryExecutionResult


def incompatible_claim(text, result):
    columns = [normalize(c) for c in result.columns]
    families = {family for family, pattern in {
        "dec": r"(?:^|_)dec(?:_|$)", "fec": r"(?:^|_)fec(?:_|$)",
        "consumo": r"consumo|energia_kwh", "receita": r"receita|valor_faturado",
    }.items() if any(re.search(pattern, col) for col in columns)}
    if len(families) == 1:
        family = next(iter(families))
        for match in re.finditer(r"\b(dec|fec|consumo|receita)\s+(?:foi|e|era|totaliza)\b", normalize(text)):
            if match[1] != family:
                return True
        if family in {"dec", "fec"} and re.search(r"\b(?:DEC|FEC)\s+(?:foi|é|era)\s+de?\s*\d[\d.,]*\s*(?:kWh|R\$|%)", text, re.I):
            return True
    if "municipio" in columns:
        index = columns.index("municipio")
        locations = {normalize(str(row[index])) for row in result.rows}
        for location in re.findall(r"\bEm ([A-ZÀ-Ý][\wÀ-ÿ ]{1,60}),", text):
            if normalize(location) not in locations:
                return True
    # Uma oração com um único mês e um único valor explícito deve corresponder
    # a uma das linhas desse mês. Não inferir associações em prosa ambígua.
    if "mes_referencia" in columns and len(columns) == 2:
        date_index = columns.index("mes_referencia")
        for clause in re.split(r"[;\n]", text):
            dates = extract_dates(clause)
            numbers = extract_numbers(clause)
            if len(dates) != 1 or len(numbers) != 1:
                continue
            date = dates[0]
            matching = [row for row in result.rows if str(row[date_index])[:7] == f"{date.year:04}-{date.month:02}"]
            if matching:
                evidence = QueryExecutionResult(columns=result.columns,rows=matching,row_count=len(matching),truncated=True)
                if not is_number_supported(numbers[0].candidates, build_allowed_numbers("", "", evidence)):
                    return True
    return False
