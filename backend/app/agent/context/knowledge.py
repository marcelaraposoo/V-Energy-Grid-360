"""Fontes curadas e versionadas, sem busca por palavra-chave na pergunta.

O modelo escolhe IDs; o backend só aceita documentos deste catálogo. Valores
operacionais nunca são recuperados aqui. O arquivo acompanha o código no Docker.
"""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("knowledge.json")


@lru_cache(maxsize=1)
def sources():
    return {item["id"]: item for item in json.loads(_PATH.read_text(encoding="utf-8"))}


def source_text(ids):
    catalog = sources()
    if any(item not in catalog for item in ids):
        raise ValueError("Fonte de conhecimento não autorizada.")
    return "\n\n".join(catalog[item]["title"] + ": " + catalog[item]["text"] for item in dict.fromkeys(ids))


def source_labels(ids):
    catalog = sources()
    return [f"{catalog[item]['title']} — {catalog[item]['source']}" for item in dict.fromkeys(ids) if item in catalog]


def knowledge_context():
    evidence = [{key: item[key] for key in ('id','title','source','text')} for item in sources().values()]
    return "\n<fontes_conhecimento>\n" + json.dumps(evidence, ensure_ascii=False).replace("<", "\\u003c") + "\n</fontes_conhecimento>"


def context_for_sources(database_context, ids):
    """Recuperação por IDs semânticos escolhidos pelo modelo, sem keywords da pergunta."""
    tables = {table for source_id in ids for table in sources()[source_id].get('tables', [])}
    headings = list(re.finditer(r'(?m)^# \d+\. `([^`]+)`\s*$', database_context))
    if not tables or not headings:
        return database_context
    sections = []
    for index, heading in enumerate(headings):
        if heading.group(1) in tables:
            end = headings[index+1].start() if index+1 < len(headings) else len(database_context)
            sections.append(database_context[heading.start():end].split('<metadados_consultados>')[0])
    metadata = ('<metadados_consultados>' + database_context.split('<metadados_consultados>',1)[1]
                if '<metadados_consultados>' in database_context else '')
    preamble = database_context.split('## Regras semânticas importantes',1)[0]
    return preamble + '\n\n'.join(sections) + '\n' + metadata


@lru_cache(maxsize=1)
def knowledge_version():
    # Invalida também alterações no schema e nas instruções; processo novo em
    # cada deploy. Nenhum dado Gold ou segredo entra neste fingerprint.
    files = [_PATH, _PATH.with_name("gold_schema_context.md")]
    files += sorted((_PATH.parent.parent / "prompts").rglob("*.md"))
    return hashlib.sha256(b"\n".join(path.read_bytes() for path in files)).hexdigest()[:16]
