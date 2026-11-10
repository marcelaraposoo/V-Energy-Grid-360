"""Metadados locais limitados, somente leitura; nunca contém cadastro pessoal."""
import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from time import monotonic
from app.core.observability import observe


def reference_date():
    # Fuso operacional brasileiro; não depende do fuso do processo servidor.
    return datetime.now(timezone(timedelta(hours=-3))).date()


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(c) != "Mn")


def requested_month(question):
    """Mês de calendário em pergunta autossuficiente; follow-up depende da memória."""
    from app.agent.context_requirement import requires_complete_question
    if requires_complete_question(question):
        return None
    text = normalize(question)
    if not re.search(r"\bmes passado\b", text):
        return None
    return (reference_date().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')


def followup_year(question, memory_context):
    """Resolve apenas ano anterior a um pedido anual explícito, sem adivinhar."""
    if normalize(question).strip(' ?.!') not in {'e no ano passado', 'e no ano anterior'}:
        return None
    turns = re.findall(r'^Usuário: (.+)$', memory_context or '', flags=re.M)
    if not turns:
        return None
    previous = normalize(turns[-1])
    years = re.findall(r'\b20\d{2}\b', previous)
    if len(years) == 1 and re.search(r'\b(?:em|ano de|ano) 20\d{2}\b(?!-)', previous):
        # Um mês/data explícito ou comparativo não autoriza assumir ano inteiro.
        if not re.search(r'20\d{2}[-/]\d|\b(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|mes|semestre|trimestre)\b', previous):
            return str(int(years[0]) - 1)
    return None


def followup_period_problem(question, memory_context, sql):
    from sqlglot import exp, parse_one
    year = followup_year(question, memory_context)
    if year is None:
        return None
    tree = parse_one(sql, read='sqlite')
    for predicate in tree.find_all(exp.EQ):
        if isinstance(predicate.this, exp.Column) and predicate.this.name == 'ano' and isinstance(predicate.expression, exp.Literal) and predicate.expression.this == year:
            return None
    for predicate in tree.find_all(exp.Between):
        if isinstance(predicate.this, exp.Column) and predicate.this.name == 'mes_referencia':
            if predicate.args['low'].is_string and predicate.args['high'].is_string and (
                predicate.args['low'].this, predicate.args['high'].this
            ) == (year+'-01', year+'-12'):
                return None
    return (f"O pedido anterior foi anual. O acompanhamento solicita todo o ano de {year}, "
            f"não apenas os meses disponíveis da resposta anterior. Filtre mes_referencia BETWEEN '{year}-01' AND '{year}-12', "
            "mantendo a métrica e a localidade anteriores.")


def relative_period_problem(question, sql):
    from sqlglot import parse_one, exp
    month = requested_month(question)
    if month is None:
        return None
    tree = parse_one(sql, read='sqlite')
    literals = []
    for where in tree.find_all(exp.Where):
        for predicate in where.find_all(exp.EQ, exp.Between, exp.GTE, exp.GT, exp.LTE, exp.LT):
            if any(c.name in {'mes_referencia', 'data_hora_inicio', 'data_hora_abertura', 'data_emissao'}
                   for c in predicate.find_all(exp.Column)):
                literals.extend(n.this for n in predicate.find_all(exp.Literal) if n.is_string)
    if not any(value == month or value.startswith(month + '-') for value in literals):
        return (f"O mês passado solicitado é {month}, relativo ao calendário atual, não ao fim da Gold. "
                f"Use limites de data literais explícitos para {month}, mesmo se não houver registros.")
    return None


@lru_cache(maxsize=4)
def _catalog(path, size, modified):
    deadline = monotonic() + 2
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=1)) as con:
        con.execute("PRAGMA query_only=ON")
        con.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
        places = con.execute("SELECT DISTINCT municipio,bairro FROM dim_uc LIMIT 5001").fetchall()
        period = con.execute("SELECT MIN(mes_referencia),MAX(mes_referencia) FROM kpis_mensal").fetchone()
    return places[:5000], period


@observe("metadata")
def build_runtime_context(question, database_path=None):
    from app.core.config import settings
    metadata = {"data_atual": reference_date().isoformat(), "fuso": "America/Sao_Paulo"}
    try:
        path = Path(database_path or settings.sqlite_path).resolve()
        stat = path.stat()
        places, period = _catalog(str(path), stat.st_size, stat.st_mtime_ns)
        metadata["cobertura_competencias"] = {"inicio": period[0], "fim": period[1]}
        metadata["municipios_cobertos"] = sorted({m for m, _ in places if m})
        from app.agent.context.place_search import contains_name, discover_neighborhoods
        matches, candidates = discover_neighborhoods(question, places)
        metadata["bairros_mencionados"] = matches[:30]
        remaining = 30
        partial = []
        for candidate in candidates:
            options = candidate['opcoes'][:remaining]
            if options:
                partial.append(dict(trecho=candidate['trecho'], opcoes=options))
                remaining -= len(options)
        metadata['bairros_candidatos'] = partial
        metadata["municipios_mencionados"] = sorted({m for m, _ in places if contains_name(m, question)})
        metadata["catalogo_parcial"] = (len(matches) > 30 or len(places) == 5000
                                         or sum(len(c['opcoes']) for c in candidates) > 30)
    except (OSError, sqlite3.Error):
        metadata["catalogo_disponivel"] = False
    payload = json.dumps(metadata, ensure_ascii=False).replace("<", "\\u003c")
    return "\n\n<metadados_consultados>\n" + payload + "\n</metadados_consultados>"
