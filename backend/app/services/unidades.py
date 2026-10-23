from __future__ import annotations

from app.core.errors import NaoEncontrado
from app.schemas import Visao360
from app.services.continuidade import dec_fec

LIMIAR_CONTA_ALTA_PCT = 15.0  # decisão do time: variação > 15% já é "consumo subiu"


def visao_360(repo, uc_id: str) -> Visao360:
    uc = repo.uc(uc_id)
    if not uc:
        raise NaoEncontrado(f"Unidade consumidora {uc_id} não encontrada")
    serie = repo.consumo_uc(uc_id)
    por_comp = {s["competencia"]: s["consumo_kwh"] for s in serie}
    ult12 = serie[-12:]
    consumo = []
    for s in ult12:
        ano, mes = s["competencia"].split("-")
        consumo.append({**s, "consumo_kwh_ano_anterior": por_comp.get(f"{int(ano) - 1}-{mes}")})

    # diagnóstico "a conta veio alta": últimos 3 meses vs. mesmos meses do ano anterior
    atual = [c["consumo_kwh"] for c in consumo[-3:]]
    anterior = [c["consumo_kwh_ano_anterior"] for c in consumo[-3:] if c["consumo_kwh_ano_anterior"] is not None]
    if anterior and sum(anterior):
        var = (sum(atual) / sum(anterior) - 1) * 100
        subiu = var > LIMIAR_CONTA_ALTA_PCT
        msg = (f"O consumo dos últimos 3 meses subiu {var:.1f}% em relação ao mesmo período do ano passado."
               if subiu else f"O consumo dos últimos 3 meses variou {var:.1f}% vs. ano anterior; não explica uma conta muito mais alta (verificar tarifa/bandeira).")
        diag = {"consumo_subiu": subiu, "variacao_pct": round(var, 1), "mensagem": msg}
    else:
        diag = {"consumo_subiu": None, "variacao_pct": None, "mensagem": "Histórico insuficiente para comparar."}

    faturas = sorted(repo.faturas_uc(uc_id), key=lambda f: f["competencia"], reverse=True)
    c = repo.competencias()
    oc = repo.ocorrencias(c[-12], c[-1], alimentador_id=uc["alimentador_id"])
    alim = next(a for a in repo.alimentadores() if a["id"] == uc["alimentador_id"])
    dec, fec = dec_fec(oc, alim["ucs_total"])
    return Visao360(
        cadastro=uc, consumo=consumo, diagnostico_conta_alta=diag, faturas=faturas[:12],
        faturas_em_aberto=[f for f in faturas if f["status"] in ("aberta", "atrasada")],
        medidor=repo.medidor_uc(uc_id), geracao_distribuida=repo.gd_uc(uc_id),
        interrupcoes={"alimentador_id": uc["alimentador_id"], "ultimos_12_meses": len(oc), "dec_horas": dec,
                      "fec_vezes": fec, "recentes": sorted(oc, key=lambda o: o["data"], reverse=True)[:5]},
        atendimentos=sorted(repo.atendimentos_uc(uc_id), key=lambda a: a["data"], reverse=True),
    )
