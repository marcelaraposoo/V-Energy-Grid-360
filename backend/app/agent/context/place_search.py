"""Busca cadastral por palavras completas; candidatos nunca autorizam uma consulta."""
import re

from app.agent.context.runtime import normalize


def words(value):
    return tuple(re.findall(r'\w+', normalize(value or '')))


def spans(needle, haystack):
    if not needle:
        return []
    return [(i, i + len(needle)) for i in range(len(haystack) - len(needle) + 1)
            if haystack[i:i + len(needle)] == needle]


def contains_name(name, text):
    return bool(spans(words(name), words(text)))


def neighborhood_candidates(name, places, municipalities=()):
    """Prefere nome exato; nome parcial gera opções, nunca expansão automática."""
    query = words(name)
    eligible = sorted({(m, b) for m, b in places if b and (not municipalities or m in municipalities)})
    exact = [(m, b) for m, b in eligible if words(b) == query]
    if exact:
        return exact
    if not any(len(word) >= 4 for word in query):
        return []
    return [(m, b) for m, b in eligible if spans(query, words(b))]


def discover_neighborhoods(question, places):
    """Recupera nomes completos e fragmentos para a interpretação semântica.

    Nomes completos/municípios ocupam seus próprios trechos. Assim, uma menção
    exata a Macaxeira não vira uma busca por Engenho Macaxeira, nem Caetés II
    vira Caetés I. Fragmentos mais longos prevalecem sobre seus componentes.
    """
    text = words(question)
    pairs = sorted({(m, b) for m, b in places if b})
    exact = [(span, (m, b)) for m, b in pairs for span in spans(words(b), text)]
    exact = [(span, pair) for span, pair in exact if not any(
        other != span and other[0] <= span[0] and other[1] >= span[1] for other, _ in exact)]
    occupied = [span for span, _ in exact]
    occupied += [span for m in {m for m, _ in pairs} for span in spans(words(m), text)]
    fragments = {}
    # Marcadores geográficos não são, sozinhos, um nome parcial identificável.
    generic = {'bairro', 'bairros', 'municipio', 'municipios', 'distrito', 'distritos'}
    connectors = {'de', 'do', 'da', 'dos', 'das', 'e', 'em', 'no', 'na', 'nos', 'nas', 'a', 'o', 'as', 'os', 'd'}
    for m, b in pairs:
        name = words(b)
        for start in range(len(name)):
            for end in range(start + 1, len(name) + 1):
                fragment = name[start:end]
                if fragment == name or not any(len(w) >= 4 and w not in generic for w in fragment):
                    continue
                # "de Suape" na pergunta não exclui nomes que contenham apenas
                # "Suape". Preposições nas bordas não distinguem localidades.
                if fragment[0] in connectors or fragment[-1] in connectors:
                    continue
                for span in spans(fragment, text):
                    if any(a <= span[0] and z >= span[1] for a, z in occupied):
                        continue
                    fragments.setdefault(span, set()).add((m, b))
    longest = [span for span in fragments if not any(
        other != span and other[0] <= span[0] and other[1] >= span[1] for other in fragments)]
    candidates = [dict(trecho=' '.join(text[a:z]), opcoes=[dict(municipio=m, bairro=b)
                  for m, b in sorted(fragments[(a, z)])]) for a, z in sorted(longest)]
    return [dict(municipio=m, bairro=b) for m, b in sorted({pair for _, pair in exact})], candidates


def candidate_message(pairs):
    selected = pairs[:8]
    while selected:
        groups = {}
        for municipality, neighborhood in selected:
            groups.setdefault(municipality, []).append(neighborhood)
        options = '; '.join(f"{m}: {', '.join(names)}" for m, names in groups.items())
        ending = (' Há outras opções. Informe o bairro e município.' if len(selected) < len(pairs)
                  else ' Qual bairro e município você deseja?')
        message = f'Encontrei no cadastro: {options}.{ending}'
        if len(message) <= 300:
            return message
        selected = selected[:-1]
    return 'Há opções de bairros no cadastro. Informe o nome completo do bairro e o município.'
