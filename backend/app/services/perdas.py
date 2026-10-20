from __future__ import annotations

from app.core.errors import ConflitoDeEstado, NaoEncontrado
from app.schemas import OrdemCreate, ResultadoInspecao, SuspeitaFila

ATIVAS = ("PENDENTE", "EM_CAMPO")


def fila(repo, municipio: str | None = None, classe: str | None = None, min_prob: float = 0.0, limite: int = 50) -> list[SuspeitaFila]:
    """Ordena por prioridade = probabilidade × energia recuperável (kWh/mês).
    Premissa do time: UCs que já têm ordem ativa saem da fila."""
    com_ordem = {o["uc_id"] for o in repo.listar_ordens() if o["status"] in ATIVAS}
    itens = []
    for s in repo.suspeitas():
        if s["uc_id"] in com_ordem or s["probabilidade"] < min_prob:
            continue
        uc = repo.uc(s["uc_id"])
        if (municipio and uc["municipio"] != municipio) or (classe and uc["classe"] != classe):
            continue
        itens.append((s["probabilidade"] * s["energia_recuperavel_kwh_mes"], s, uc))
    itens.sort(key=lambda x: x[0], reverse=True)
    return [
        SuspeitaFila(posicao=i + 1, uc_id=s["uc_id"], titular=uc["titular"], municipio=uc["municipio"],
                     bairro=uc["bairro"], classe=uc["classe"], motivos=s["motivos"], probabilidade=s["probabilidade"],
                     energia_recuperavel_kwh_mes=s["energia_recuperavel_kwh_mes"], prioridade_score=round(score, 1))
        for i, (score, s, uc) in enumerate(itens[:limite])
    ]


def _ordem(repo, ordem_id: int) -> dict:
    o = repo.obter_ordem(ordem_id)
    if not o:
        raise NaoEncontrado(f"Ordem {ordem_id} não encontrada")
    return o


def criar(repo, dados: OrdemCreate) -> dict:
    if not repo.uc(dados.uc_id):
        raise NaoEncontrado(f"Unidade consumidora {dados.uc_id} não encontrada")
    if any(o["uc_id"] == dados.uc_id.upper() and o["status"] in ATIVAS for o in repo.listar_ordens()):
        raise ConflitoDeEstado("Já existe ordem de inspeção ativa para esta unidade")
    return repo.criar_ordem({"uc_id": dados.uc_id.upper(), "motivo": dados.motivo, "observacoes": dados.observacoes})


def iniciar(repo, ordem_id: int) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] != "PENDENTE":
        raise ConflitoDeEstado(f"Só é possível enviar a campo ordens PENDENTES (status atual: {o['status']})")
    return repo.atualizar_ordem(ordem_id, {"status": "EM_CAMPO"})


def registrar_resultado(repo, ordem_id: int, r: ResultadoInspecao) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] not in ATIVAS:
        raise ConflitoDeEstado(f"Ordem {o['status']} não aceita resultado")
    return repo.atualizar_ordem(ordem_id, {"status": "CONCLUIDA", "resultado": r.model_dump()})


def cancelar(repo, ordem_id: int) -> dict:
    o = _ordem(repo, ordem_id)
    if o["status"] not in ATIVAS:
        raise ConflitoDeEstado(f"Ordem {o['status']} não pode ser cancelada")
    return repo.atualizar_ordem(ordem_id, {"status": "CANCELADA"})
