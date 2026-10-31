from app.core.errors import NaoEncontrado
from app.schemas import AbaFaturas, PaginaFaturasUC, SituacaoFaturas


def listar(repo, uc_id: str, aba: AbaFaturas, ano: int | None,
           situacao: SituacaoFaturas, pagina: int) -> PaginaFaturasUC:
    if not repo.uc(uc_id):
        raise NaoEncontrado(f"Unidade consumidora {uc_id} não encontrada")
    if aba != "historico" and (ano is not None or situacao != "todas"):
        raise ValueError("Os filtros de ano e situação só se aplicam ao histórico completo.")
    return PaginaFaturasUC.model_validate(repo.pagina_faturas_uc(uc_id, aba, ano, situacao, pagina))
