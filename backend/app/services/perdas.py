from __future__ import annotations

import unicodedata

from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.schemas import Insight, OrdemCreate, ResultadoInspecao, SuspeitaFila

ATIVAS = ("PENDENTE", "EM_CAMPO")
CAPACIDADE_MENSAL = 200  # do case: a equipe de perdas consegue "mais de 200 inspeções por mês"


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para a busca ('joao' encontra 'João')."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sem_acento.casefold().strip()


def fila(repo, municipio: str | None = None, classe: str | None = None, min_prob: float = 0.0,
         q: str | None = None, pagina: int = 1, tamanho: int = 20) -> tuple[list[SuspeitaFila], int]:
    """Fila de suspeitas ordenada por prioridade = probabilidade × energia recuperável (kWh/mês).

    Devolve (itens da página, total de itens após os filtros). A `posicao` é o lugar na fila já filtrada,
    contado desde o primeiro item (a página 2 começa em tamanho + 1).
    Quando a fonte já traz a posição (`prioridade`) e o `score` calculados pela Gold, essa ordem é respeitada e o
    score é exibido como prioridade; sem eles (mock), vale a conta acima.
    Premissa do time: UCs que já têm ordem ativa saem da fila.
    A busca `q` procura no número da UC e no nome do titular, sem diferenciar maiúsculas nem acentos."""
    com_ordem = {o["uc_id"] for o in repo.listar_ordens() if o["status"] in ATIVAS}
    termo = normalizar(q) if q else ""
    itens = []
    for s in repo.suspeitas():
        if s["uc_id"] in com_ordem or s["probabilidade"] < min_prob:
            continue
        uc = repo.uc(s["uc_id"])
        if uc is None:  # suspeita de uma UC que não está no cadastro: não dá para localizar nem inspecionar
            continue
        if (municipio and uc["municipio"] != municipio) or (classe and uc["classe"] != classe):
            continue
        if termo and termo not in normalizar(uc["uc_id"]) and termo not in normalizar(uc["titular"]):
            continue
        score = s["score"] if s.get("score") is not None else s["probabilidade"] * s["energia_recuperavel_kwh_mes"]
        itens.append((s.get("prioridade"), score, s, uc))
    itens.sort(key=lambda x: (x[0] if x[0] is not None else float("inf"), -x[1]))
    inicio = (pagina - 1) * tamanho
    pagina_itens = [
        SuspeitaFila(posicao=inicio + i + 1, uc_id=s["uc_id"], titular=uc["titular"], municipio=uc["municipio"],
                     bairro=uc["bairro"], classe=uc["classe"], motivos=s["motivos"], probabilidade=s["probabilidade"],
                     energia_recuperavel_kwh_mes=s["energia_recuperavel_kwh_mes"], prioridade_score=round(score, 1))
        for i, (_, score, s, uc) in enumerate(itens[inicio:inicio + tamanho])
    ]
    return pagina_itens, len(itens)


def _pt(valor: float) -> str:
    """12345.6 -> '12.346' (separador de milhar brasileiro, sem casas decimais)."""
    return f"{valor:,.0f}".replace(",", ".")


def insights_fila(repo) -> list[Insight]:
    """Insights da tela de perdas, calculados direto da fila (fiéis por construção: só somas e contagens).

    Usa a fila como ela está agora (UCs com ordem ativa já ficam de fora) e a capacidade de 200 inspeções/mês
    informada no case. Lista vazia quando não há suspeitas.
    """
    itens, total = fila(repo, tamanho=max(1, len(repo.suspeitas())))
    if total == 0:
        return []
    energia_total = sum(i.energia_recuperavel_kwh_mes for i in itens)
    foco = itens[:CAPACIDADE_MENSAL]
    energia_foco = sum(i.energia_recuperavel_kwh_mes for i in foco)
    cobertura = energia_foco / energia_total * 100 if energia_total else 0.0
    resultado = [Insight(
        tipo="destaque",
        texto=(f"A fila tem {_pt(total)} unidades suspeitas, com {_pt(energia_total)} kWh/mês a recuperar. "
               f"Inspecionar as {_pt(len(foco))} primeiras (capacidade de cerca de {CAPACIDADE_MENSAL} inspeções por mês) "
               f"cobre {cobertura:.0f}% desse potencial ({_pt(energia_foco)} kWh/mês)."),
        dados={"unidades_na_fila": total, "energia_total_kwh_mes": round(energia_total, 1),
               "capacidade_mensal": CAPACIDADE_MENSAL, "unidades_foco": len(foco),
               "energia_foco_kwh_mes": round(energia_foco, 1), "cobertura_pct": round(cobertura, 1)},
    )]
    por_municipio: dict[str, int] = {}
    for i in foco:
        por_municipio[i.municipio] = por_municipio.get(i.municipio, 0) + 1
    municipio, qtd = max(por_municipio.items(), key=lambda kv: (kv[1], kv[0]))
    resultado.append(Insight(
        tipo="informativo",
        texto=f"{municipio} concentra {_pt(qtd)} das {_pt(len(foco))} unidades mais promissoras da fila.",
        dados={"municipio": municipio, "unidades": qtd, "unidades_foco": len(foco)},
    ))
    return resultado


def _ordem(repo, ordem_id: int) -> dict:
    o = repo.obter_ordem(ordem_id)
    if not o:
        raise NaoEncontrado(f"Ordem {ordem_id} não encontrada")
    return o


def obter(repo, ordem_id: int) -> dict:
    return _ordem(repo, ordem_id)


def criar(repo, dados: OrdemCreate) -> dict:
    if not repo.uc(dados.uc_id):
        raise NaoEncontrado(f"Unidade consumidora {dados.uc_id} não encontrada")
    if any(o["uc_id"] == dados.uc_id.upper() and o["status"] in ATIVAS for o in repo.listar_ordens()):
        raise ConflitoDeEstado("Já existe ordem de inspeção ativa para esta unidade")
    return repo.criar_ordem({"uc_id": dados.uc_id.upper(), "motivo": dados.motivo, "observacoes": dados.observacoes})


def iniciar(repo, ordem_id: int) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] != "PENDENTE":
        raise ConflitoDeEstado(f"Só é possível enviar a campo ordens PENDENTES. A ordem {ordem_id} está {o['status']}.")
    return repo.atualizar_ordem(ordem_id, {"status": "EM_CAMPO"})


def registrar_resultado(repo, ordem_id: int, r: ResultadoInspecao) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] not in ATIVAS:
        raise ConflitoDeEstado(f"A ordem {ordem_id} está {o['status']} e não aceita resultado (só PENDENTE ou EM_CAMPO).")
    return repo.atualizar_ordem(ordem_id, {"status": "CONCLUIDA", "resultado": r.model_dump()})


def cancelar(repo, ordem_id: int) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] not in ATIVAS:
        raise ConflitoDeEstado(f"A ordem {ordem_id} está {o['status']} e não pode ser cancelada (só PENDENTE ou EM_CAMPO).")
    return repo.atualizar_ordem(ordem_id, {"status": "CANCELADA"})
