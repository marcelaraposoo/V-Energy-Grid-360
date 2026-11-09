"""Resolução cadastral, independente da formulação da pergunta.

Só equivalência de acentos/caixa/espaços é aplicada automaticamente. Aproximações
pedem confirmação; ausência no cadastro não afirma inexistência no mundo real.
"""
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from sqlglot import exp, parse_one

from app.agent.context.runtime import _catalog, normalize
from app.agent.context.place_search import (
    candidate_message, contains_name, discover_neighborhoods, neighborhood_candidates, words,
)
from app.agent.schemas import SemanticIntent
from app.core.observability import observe


def name_key(value):
    return " ".join(normalize(value).split())


def load_places(database_path=None):
    from app.core.config import settings
    path = Path(database_path or settings.sqlite_path).resolve()
    stat = path.stat()
    return _catalog(str(path), stat.st_size, stat.st_mtime_ns)[0]


@dataclass(frozen=True)
class Resolution:
    sql: str
    status: str
    message: str | None = None
    entities: tuple[str, ...] = ()


def _candidate_resolution(intent, places, question='', memory_context=None):
    evidence = question + (' ' + (memory_context or '') if intent.uses_context else '')
    municipalities = {m for m, _ in places if any(
        ref.kind == 'municipio' and name_key(ref.name) == name_key(m) and contains_name(m, evidence)
        for ref in intent.locations)}
    for ref in intent.locations:
        if ref.kind == 'municipio' and any(name_key(ref.name) == name_key(m) for m, _ in places):
            continue
        if question and not contains_name(ref.name, evidence):
            continue
        options = neighborhood_candidates(ref.name, places, municipalities)
        exact = options and words(options[0][1]) == words(ref.name)
        if options and (not exact or len(options) > 1 or ref.kind != 'bairro'):
            return Resolution('', 'ambiguous' if exact and len(options) > 1 else 'candidates', candidate_message(options),
                              tuple(f'bairro={b}; municipio={m}' for m, b in options[:8]))
    return None


@observe('entities')
def clarify_geography(intent, database_path=None, question='', memory_context=None):
    """Enriquece um esclarecimento já pedido pelo modelo; nunca libera execução."""
    if not intent.locations:
        return None
    return _candidate_resolution(intent, load_places(database_path), question, memory_context)


@observe("entities")
def resolve_geography(sql: str, intent: SemanticIntent, database_path=None, question=None, memory_context=None) -> Resolution:
    tree = parse_one(sql, read="sqlite")
    literals = []
    for predicate in tree.find_all(exp.EQ, exp.In):
        left = predicate.this
        column = left if isinstance(left, exp.Column) else left.find(exp.Column)
        if column is None or column.name.lower() not in {"municipio", "bairro"}:
            continue
        values = [predicate.expression] if isinstance(predicate, exp.EQ) else predicate.expressions
        literals.extend((column.name.lower(), value) for value in values
                        if isinstance(value, exp.Literal) and value.is_string)
    references = [(item.kind, item.name) for item in intent.locations]
    references += [(kind, literal.this) for kind, literal in literals]
    if not references:
        return Resolution(sql, "not_required")
    places = load_places(database_path)  # Exceções são falha técnica, nunca ausência.
    candidates = _candidate_resolution(intent, places, question or '', memory_context)
    if candidates is not None:
        return Resolution(sql, candidates.status, candidates.message, candidates.entities)
    if question is not None:
        evidence = name_key(question + (' ' + (memory_context or '') if intent.uses_context else ''))
        for kind,name in references:
            if contains_name(name, evidence):
                continue
            # Um bairro cadastrado em município único prova o pai geográfico,
            # mesmo quando o usuário não escreveu o município redundante.
            owners = {m for m,b in places if b and contains_name(b, evidence)}
            if kind=='municipio' and len(owners)==1 and name_key(next(iter(owners)))==name_key(name):
                continue
            _, partial = discover_neighborhoods(question, places)
            options = sorted({(o['municipio'], o['bairro']) for group in partial for o in group['opcoes']})
            if options:
                return Resolution(sql, 'candidates', candidate_message(options))
            return Resolution(sql, "unverified_reference", "Confirme a grafia da localidade desejada para eu consultar o cadastro com segurança.")
    municipalities = {m for m, _ in places if m}
    neighborhoods = {b for _, b in places if b}
    canonical = {}
    resolved = []
    selected_municipalities = {m for m in municipalities if any(
        kind == "municipio" and name_key(name) == name_key(m) for kind, name in references)}
    for kind, name in dict.fromkeys(references):
        universe = municipalities if kind == "municipio" else neighborhoods
        matches = sorted(value for value in universe if name_key(value) == name_key(name))
        if not matches:
            candidates = get_close_matches(name_key(name), sorted({name_key(v) for v in universe}), n=3, cutoff=.82)
            suggestions = sorted(v for v in universe if name_key(v) in candidates)
            if suggestions:
                return Resolution(sql, "suggestion", f"Você quis dizer {', '.join(suggestions)}? Confirme a localidade para consultar os dados.")
            if len(places) >= 5000:
                return Resolution(sql, "catalog_partial", "O catálogo disponível é parcial; não consegui confirmar essa localidade. Informe o município e o bairro.")
            return Resolution(sql, "not_covered", f"A localidade informada não consta entre os {('municípios' if kind == 'municipio' else 'bairros')} cobertos pelo cadastro disponível. Isso não significa que ela não exista. Informe outra localidade da base.")
        if kind == "bairro":
            owners = {m for m, b in places if b in matches}
            if selected_municipalities:
                owners &= selected_municipalities
            if not owners:
                return Resolution(sql, "invalid_pair", "O bairro e o município informados não correspondem ao mesmo cadastro. Confirme a combinação desejada.")
            if len(owners) > 1:
                return Resolution(sql, "ambiguous", f"Esse bairro aparece em mais de um município: {', '.join(sorted(owners))}. Qual deles você deseja consultar?")
        if len(matches) != 1:
            return Resolution(sql, "ambiguous", "Há mais de uma grafia cadastral compatível. Confirme o município e o bairro desejados.")
        canonical[(kind, name_key(name))] = matches[0]
        resolved.append(f"{kind}={matches[0]}")
    # Reescrita somente de literais do AST, nunca interpolação em SQL.
    changed = False
    for kind, literal in literals:
        value = canonical[(kind, name_key(literal.this))]
        # LOWER/UPPER já expressa normalização SQL: preserve a forma esperada.
        predicate = literal.parent
        if predicate is not None and isinstance(predicate.this, exp.Upper):
            value = value.upper()
        elif predicate is not None and isinstance(predicate.this, exp.Lower):
            value = value.lower()
        if literal.this != value:
            literal.set("this", value)
            changed = True
    return Resolution(tree.sql(dialect="sqlite") if changed else sql, "available", entities=tuple(dict.fromkeys(resolved)))
