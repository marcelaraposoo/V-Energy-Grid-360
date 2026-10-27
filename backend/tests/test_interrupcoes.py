from datetime import datetime, timedelta

import pytest

from app.repositories.mock_repo import MockRepository
from app.mock.mock_data import build_dec_fec_alimentador_mensal
from app.services.unidades import visao_360


@pytest.fixture
def cenario(monkeypatch):
    repo = MockRepository()
    ucs = repo.d["dim_uc"]
    uc = ucs[0]
    vizinhas = [u for u in ucs[1:] if u["alimentador"] == uc["alimentador"]]
    outra = next(u for u in ucs if u["alimentador"] != uc["alimentador"])
    eventos = []

    def adicionar(cadastro, data, causa=None):
        inicio = datetime.fromisoformat(data)
        eventos.append({
            "id_ocorrencia": f"OC{len(eventos) + 1:06d}", "id_uc": cadastro["id_uc"],
            "alimentador": cadastro["alimentador"], "municipio": cadastro["municipio"],
            "bairro": cadastro["bairro"], "classe": cadastro["classe"],
            "tipo": "FALTA DE ENERGIA", "causa": causa, "causa_evitavel": causa == "VEGETACAO",
            "data_hora_inicio": data,
            "data_hora_fim": (inicio + timedelta(hours=1)).isoformat(),
            "mes_referencia": data[:7], "duracao_min": 60,
        })

    adicionar(uc, "2025-06-30T22:00:00")
    adicionar(uc, "2025-07-01T00:00:00")
    for dia in range(10, 15):
        adicionar(uc, f"2026-01-{dia}T22:35:12")
    adicionar(uc, "2026-06-30T22:00:00")
    adicionar(uc, "2026-07-01T00:00:00")
    adicionar(vizinhas[0], "2026-06-30T22:00:00", causa="VEGETACAO")
    adicionar(outra, "2026-06-30T22:00:00")
    monkeypatch.setitem(repo.d, "fato_interrupcao", list(reversed(eventos)))
    monkeypatch.setitem(repo.d, "dec_fec_alimentador_mensal", build_dec_fec_alimentador_mensal(
        ucs, eventos, repo.alimentadores(), repo.competencias(),
    ))
    return repo, uc, vizinhas[1]


def test_repositorio_filtra_uc_e_periodo_inclusive_limites(cenario):
    repo, uc, _ = cenario
    registros = repo.ocorrencias("2025-07", "2026-06", uc_id=uc["id_uc"].lower())

    assert len(registros) == 7
    assert {o["uc_id"] for o in registros} == {uc["id_uc"]}
    assert min(o["data"] for o in registros) == "2025-07-01T00:00:00"
    assert max(o["data"] for o in registros) == "2026-06-30T22:00:00"
    assert all(o["duracao_min"] == 60 and o["uc_id"] == uc["id_uc"] for o in registros)


def test_visao_360_nao_mistura_ucs_e_ordena_historico(cenario):
    repo, uc, _ = cenario
    interrupcoes = visao_360(repo, uc["id_uc"]).interrupcoes

    assert interrupcoes.escopo == "uc"
    assert interrupcoes.qtd_ocorrencias == 7
    assert len(interrupcoes.historico) == 7
    assert {o.uc_id for o in interrupcoes.historico} == {uc["id_uc"]}
    assert [o.data.isoformat() for o in interrupcoes.historico] == [
        "2026-06-30T22:00:00", "2026-01-14T22:35:12", "2026-01-13T22:35:12",
        "2026-01-12T22:35:12", "2026-01-11T22:35:12",
        "2026-01-10T22:35:12", "2025-07-01T00:00:00",
    ]
    assert all(o.causa is None for o in interrupcoes.historico)
    assert interrupcoes.historico[-1].data_fim.isoformat() == "2025-07-01T01:00:00"


def test_dec_fec_continua_sendo_contexto_do_alimentador(cenario):
    repo, uc, _ = cenario
    interrupcoes = visao_360(repo, uc["id_uc"]).interrupcoes
    alimentador = next(a for a in repo.alimentadores() if a["id"] == uc["alimentador"])

    # Sete ocorrências da UC e uma de outra UC do mesmo alimentador, todas de uma hora.
    assert interrupcoes.dec_horas == round(8 / alimentador["ucs_total"], 6)
    assert interrupcoes.fec_vezes == round(8 / alimentador["ucs_total"], 6)


def test_uc_sem_interrupcoes_nao_herda_ocorrencias_das_vizinhas(cenario):
    repo, _, sem_interrupcoes = cenario
    interrupcoes = visao_360(repo, sem_interrupcoes["id_uc"]).interrupcoes

    assert interrupcoes.escopo == "uc"
    assert interrupcoes.qtd_ocorrencias == 0
    assert interrupcoes.duracao_total_min == 0
    assert interrupcoes.historico == []
    assert interrupcoes.dec_horas > 0


def test_base_sem_competencias_retorna_historico_vazio(cenario, monkeypatch):
    repo, uc, _ = cenario
    monkeypatch.setattr(repo, "competencias", lambda: [])
    interrupcoes = visao_360(repo, uc["id_uc"]).interrupcoes

    assert interrupcoes.qtd_ocorrencias == 0
    assert interrupcoes.historico == []
    assert interrupcoes.dec_horas == 0
    assert interrupcoes.fec_vezes == 0
    assert interrupcoes.periodo_inicio is None
    assert interrupcoes.periodo_fim is None


@pytest.mark.parametrize(("periodo", "inicio", "quantidade", "meses", "qtd_alimentador"), [
    ("6_meses", "2026-01", 6, 6, 7),
    ("12_meses", "2025-07", 7, 12, 8),
    ("todos", "2022-07", 8, 48, 9),
])
def test_filtro_compartilhado_atualiza_uc_e_alimentador(
    cenario, periodo, inicio, quantidade, meses, qtd_alimentador,
):
    repo, uc, _ = cenario
    padrao = visao_360(repo, uc["id_uc"])
    resposta = visao_360(repo, uc["id_uc"], periodo_interrupcoes=periodo)
    interrupcoes = resposta.interrupcoes
    alimentador = next(a for a in repo.alimentadores() if a["id"] == uc["alimentador"])

    assert padrao.interrupcoes.periodo == "12_meses"
    assert interrupcoes.periodo == periodo
    assert interrupcoes.periodo_inicio == inicio
    assert interrupcoes.periodo_fim == "2026-06"
    assert interrupcoes.qtd_ocorrencias == len(interrupcoes.historico) == quantidade
    assert interrupcoes.duracao_total_min == quantidade * 60
    assert all(inicio <= o.competencia <= "2026-06" for o in interrupcoes.historico)
    mensais = repo.indicadores_continuidade(inicio, "2026-06", alimentador_id=uc["alimentador"])
    assert len(mensais) == meses
    assert sum(r["horas_interrompidas"] for r in mensais) == qtd_alimentador
    assert interrupcoes.dec_horas == round(qtd_alimentador / alimentador["ucs_total"], 6)
    assert interrupcoes.fec_vezes == round(qtd_alimentador / alimentador["ucs_total"], 6)
    assert resposta.model_dump(exclude={"interrupcoes"}) == padrao.model_dump(exclude={"interrupcoes"})
