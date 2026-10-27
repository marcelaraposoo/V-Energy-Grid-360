from __future__ import annotations

import unicodedata

from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.schemas import OrdemCreate, ResultadoInspecao, SuspeitaFila

ATIVAS = ("PENDENTE", "EM_CAMPO")


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para a busca ('joao' encontra 'João')."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sem_acento.casefold().strip()


def fila(repo, municipio: str | None = None, classe: str | None = None, min_prob: float = 0.0,
         q: str | None = None, pagina: int = 1, tamanho: int = 20) -> tuple[list[SuspeitaFila], int]:
    """Fila de suspeitas ordenada por prioridade = probabilidade × energia recuperável (kWh/mês).

    Devolve (itens da página, total de itens após os filtros). A `posicao` é o lugar na fila já filtrada,
    contado desde o primeiro item (a página 2 começa em tamanho + 1).
    Premissa do time: UCs que já têm ordem ativa saem da fila.
    A busca `q` procura no número da UC e no nome do titular, sem diferenciar maiúsculas nem acentos."""
    com_ordem = {o["uc_id"] for o in repo.listar_ordens() if o["status"] in ATIVAS}
    termo = normalizar(q) if q else ""
    itens = []
    for s in repo.suspeitas():
        if s["uc_id"] in com_ordem or s["probabilidade"] < min_prob:
            continue
        uc = repo.uc(s["uc_id"])
        if (municipio and uc["municipio"] != municipio) or (classe and uc["classe"] != classe):
            continue
        if termo and termo not in normalizar(uc["uc_id"]) and termo not in normalizar(uc["titular"]):
            continue
        itens.append((s["probabilidade"] * s["energia_recuperavel_kwh_mes"], s, uc))
    itens.sort(key=lambda x: x[0], reverse=True)
    inicio = (pagina - 1) * tamanho
    pagina_itens = [
        SuspeitaFila(posicao=inicio + i + 1, uc_id=s["uc_id"], titular=uc["titular"], municipio=uc["municipio"],
                     bairro=uc["bairro"], classe=uc["classe"], motivos=s["motivos"], probabilidade=s["probabilidade"],
                     energia_recuperavel_kwh_mes=s["energia_recuperavel_kwh_mes"], prioridade_score=round(score, 1))
        for i, (score, s, uc) in enumerate(itens[inicio:inicio + tamanho])
    ]
    return pagina_itens, len(itens)


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
