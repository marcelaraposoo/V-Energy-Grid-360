from collections import defaultdict

import pytest

from app.mock.mock_data import build_dec_fec_alimentador_mensal, build_mock_data
from app.schemas import Periodo
from app.services.continuidade import resumo_periodo, serie_mensal
from app.repositories.mock_repo import MockRepository


def test_mock_a8_tem_grade_completa_e_formulas_da_gold():
    dados = build_mock_data()
    linhas = dados["dec_fec_alimentador_mensal"]
    campos = set("""
        alimentador municipio mes_referencia qtd_ucs_alimentador_mes qtd_interrupcoes
        horas_interrompidas qtd_interrupcoes_evitaveis horas_causas_evitaveis dec_horas
        fec dec_12m_horas fec_12m causa_principal ranking_dec_mes
    """.split())
    ocorrencias = defaultdict(list)
    for o in dados["fato_interrupcao"]:
        ocorrencias[o["alimentador"], o["mes_referencia"]].append(o)
    por_alim = defaultdict(list)
    por_mes = defaultdict(list)
    assert len(linhas) == len(dados["alimentadores"]) * 48
    assert len({(r["alimentador"], r["mes_referencia"]) for r in linhas}) == len(linhas)
    for r in linhas:
        assert set(r) == campos
        registros = ocorrencias[r["alimentador"], r["mes_referencia"]]
        base = sum(u["alimentador"] == r["alimentador"] and u["data_ligacao"][:7] <= r["mes_referencia"] for u in dados["dim_uc"])
        horas = sum(o["duracao_min"] for o in registros) / 60
        assert r["qtd_ucs_alimentador_mes"] == base
        assert r["qtd_interrupcoes"] == len(registros)
        assert r["horas_interrompidas"] == pytest.approx(horas)
        assert r["dec_horas"] == pytest.approx(horas / base if base else 0)
        assert r["fec"] == pytest.approx(len(registros) / base if base else 0)
        evitaveis = [o for o in registros if o["causa_evitavel"]]
        assert r["qtd_interrupcoes_evitaveis"] == len(evitaveis)
        assert r["horas_causas_evitaveis"] == pytest.approx(sum(o["duracao_min"] for o in evitaveis) / 60)
        conhecidas = defaultdict(int)
        for o in registros:
            if o["causa"] is not None:
                conhecidas[o["causa"]] += o["duracao_min"]
        if conhecidas:
            assert conhecidas[r["causa_principal"]] == max(conhecidas.values())
        else:
            assert r["causa_principal"] is None
        if not registros:
            assert r["dec_horas"] == r["fec"] == r["horas_interrompidas"] == 0
        por_alim[r["alimentador"]].append(r)
        por_mes[r["mes_referencia"]].append(r)
    for historico in por_alim.values():
        historico.sort(key=lambda r: r["mes_referencia"])
        for i, r in enumerate(historico):
            assert r["dec_12m_horas"] == pytest.approx(sum(m["dec_horas"] for m in historico[max(0, i - 11):i + 1]))
            assert r["fec_12m"] == pytest.approx(sum(m["fec"] for m in historico[max(0, i - 11):i + 1]))
    for registros in por_mes.values():
        ordenados = sorted(registros, key=lambda r: r["ranking_dec_mes"])
        assert [r["ranking_dec_mes"] for r in ordenados] == list(range(1, len(registros) + 1))
        assert [r["dec_horas"] for r in ordenados] == sorted((r["dec_horas"] for r in registros), reverse=True)
    for a in dados["alimentadores"]:
        assert a["ucs_total"] == sum(u["alimentador"] == a["id"] for u in dados["dim_uc"])
    assert sum(a["ucs_total"] for a in dados["alimentadores"]) == 400


def cenario_mensal():
    alimentadores = [{"id": "AL1", "municipio": "Recife"}, {"id": "AL2", "municipio": "Olinda"}]
    ucs = [
        {"alimentador": "AL1", "data_ligacao": "2024-01-01"},
        {"alimentador": "AL1", "data_ligacao": "2025-02-28"},
        {"alimentador": "AL2", "data_ligacao": "2024-01-01"},
    ]
    fatos = [
        {"alimentador": "AL1", "mes_referencia": "2025-01", "duracao_min": 60, "causa": None, "causa_evitavel": False, "tipo": "OSCILACAO"},
        {"alimentador": "AL1", "mes_referencia": "2025-02", "duracao_min": 60, "causa": "VEGETACAO", "causa_evitavel": True, "tipo": "FALTA DE ENERGIA"},
        {"alimentador": "AL2", "mes_referencia": "2025-02", "duracao_min": 180, "causa": "CLIMATICA", "causa_evitavel": False, "tipo": "FALTA DE ENERGIA"},
    ]
    meses = ["2025-01", "2025-02", "2025-03"]
    return build_dec_fec_alimentador_mensal(ucs, fatos, alimentadores, meses)


def test_denominador_muda_no_mes_da_ligacao_e_meses_sem_ocorrencia_tem_zero():
    linhas = [r for r in cenario_mensal() if r["alimentador"] == "AL1"]
    assert [r["qtd_ucs_alimentador_mes"] for r in linhas] == [1, 2, 2]
    assert [r["dec_horas"] for r in linhas] == [1, 0.5, 0]
    assert [r["fec"] for r in linhas] == [1, 0.5, 0]
    assert linhas[-1]["dec_12m_horas"] == 1.5
    assert linhas[-1]["fec_12m"] == 1.5
    resumo = resumo_periodo(linhas)
    assert resumo["dec_horas"] == 1.5
    assert resumo["fec_vezes"] == 1.5
    assert resumo["horas_interrompidas"] == 2
    assert resumo["qtd_ucs_alimentador_mes"] == 2
    assert resumo["competencia_base_ucs"] == "2025-03"


def test_regiao_pondera_alimentadores_por_base_mensal():
    resumo = resumo_periodo(cenario_mensal())
    # Janeiro: 1 h / 2 UCs. Fevereiro: 4 h / 3 UCs. Março: zero.
    assert resumo["dec_horas"] == pytest.approx(0.5 + 4 / 3, abs=1e-6)
    assert resumo["fec_vezes"] == pytest.approx(0.5 + 2 / 3, abs=1e-6)
    assert resumo["horas_interrompidas"] == 5
    assert resumo["qtd_ucs_alimentador_mes"] == 3


def test_oscilacao_e_causa_nula_permanecem_no_calculo():
    janeiro = next(r for r in cenario_mensal() if r["alimentador"] == "AL1" and r["mes_referencia"] == "2025-01")
    assert janeiro["qtd_interrupcoes"] == 1
    assert janeiro["dec_horas"] == janeiro["fec"] == 1
    assert janeiro["causa_principal"] is None
    assert janeiro["qtd_interrupcoes_evitaveis"] == 0


def test_acumulado_12m_descarta_o_mes_que_sai_da_janela():
    meses = [f"2025-{m:02d}" for m in range(1, 13)] + ["2026-01"]
    ucs = [{"alimentador": "AL1", "data_ligacao": "2024-01-01"}]
    fatos = [{"alimentador": "AL1", "mes_referencia": "2025-01", "duracao_min": 60, "causa": None, "causa_evitavel": False}]
    linhas = build_dec_fec_alimentador_mensal(ucs, fatos, [{"id": "AL1", "municipio": "Recife"}], meses)
    assert linhas[-2]["dec_12m_horas"] == linhas[-2]["fec_12m"] == 1
    assert linhas[-1]["dec_12m_horas"] == linhas[-1]["fec_12m"] == 0


def test_base_zero_sem_ocorrencias_nao_divide_por_zero():
    linhas = build_dec_fec_alimentador_mensal([], [], [{"id": "AL1", "municipio": "Recife"}], ["2025-01"])
    assert linhas[0]["qtd_ucs_alimentador_mes"] == 0
    assert linhas[0]["dec_horas"] == linhas[0]["fec"] == 0
    assert resumo_periodo(linhas)["dec_horas"] == 0


def test_serie_preserva_a8_e_filtros():
    repo = MockRepository()
    serie = serie_mensal(repo, "AL001", Periodo(inicio="2025-07", fim="2026-06"))
    assert len(serie) == 12
    assert [r["competencia"] for r in serie] == [f"2025-{m:02d}" for m in range(7, 13)] + [f"2026-{m:02d}" for m in range(1, 7)]
    assert all(r["alimentador"] == "AL001" and r["fec_vezes"] == r["fec"] for r in serie)
    assert all("qtd_ucs_alimentador_mes" in r and "horas_interrompidas" in r for r in serie)
    assert serie_mensal(repo, "AL001", Periodo(inicio="2030-01", fim="2030-12")) == []
    assert repo.indicadores_continuidade("2025-07", "2026-06", alimentador_id="AL001", municipio="Olinda") == []


def test_acumulado_usa_indices_da_gold_sem_recalcular_com_horas_arredondadas():
    linhas = [
        {"mes_referencia": "2026-01", "qtd_ucs_alimentador_mes": 20,
         "horas_interrompidas": 0.02, "qtd_interrupcoes": 1, "dec_horas": 0.0008, "fec": 0.05},
        {"mes_referencia": "2026-02", "qtd_ucs_alimentador_mes": 40,
         "horas_interrompidas": 0.02, "qtd_interrupcoes": 1, "dec_horas": 0.0004, "fec": 0.025},
    ]
    resumo = resumo_periodo(linhas)
    assert resumo["dec_horas"] == 0.0012
    assert resumo["fec_vezes"] == 0.075
    assert resumo["horas_interrompidas"] == 0.04
    assert resumo["qtd_ucs_alimentador_mes"] == 40
    assert resumo["competencia_base_ucs"] == "2026-02"


def test_resumo_consolida_recorte_serie_e_causas():
    from app.services.continuidade import resumo
    repo = MockRepository()
    atual, base = Periodo(inicio="2025-07", fim="2026-06"), Periodo(inicio="2022-07", fim="2023-06")
    r = resumo(repo, atual, base)
    linhas = repo.indicadores_continuidade("2025-07", "2026-06")
    esperado = resumo_periodo(linhas)
    assert r.atual.dec_horas == esperado["dec_horas"] and r.atual.fec_vezes == esperado["fec_vezes"]
    assert r.atual.qtd_interrupcoes == esperado["n_ocorrencias"]
    assert r.atual.horas_causas_evitaveis == pytest.approx(sum(l["horas_causas_evitaveis"] for l in linhas))
    assert r.qtd_alimentadores == len(repo.alimentadores())
    assert len(r.serie) == len(r.serie_base) == 12
    # O DEC do período é a soma dos DEC mensais da região.
    assert sum(p.dec_horas for p in r.serie) == pytest.approx(r.atual.dec_horas, abs=1e-5)
    assert sum(c.qtd_interrupcoes for c in r.causas) == r.atual.qtd_interrupcoes
    assert sum(c.horas for c in r.causas) == pytest.approx(r.atual.horas_interrompidas, abs=0.1)
    assert [c.horas for c in r.causas] == sorted((c.horas for c in r.causas), reverse=True)
    assert sum(c.pct_horas for c in r.causas) == pytest.approx(100, abs=0.1)


def test_resumo_filtra_alimentador_e_aceita_sem_referencia():
    from app.services.continuidade import resumo
    repo = MockRepository()
    r = resumo(repo, Periodo(inicio="2025-07", fim="2026-06"), None, alimentador_id="AL001")
    assert r.base is None and r.serie_base == [] and r.qtd_alimentadores == 1
    serie = serie_mensal(repo, "AL001", Periodo(inicio="2025-07", fim="2026-06"))
    assert [p.dec_horas for p in r.serie] == pytest.approx([s["dec_horas"] for s in serie], abs=1e-6)
    vazio = resumo(repo, Periodo(inicio="2025-07", fim="2026-06"), None, municipio="Recife", alimentador_id="NAO-EXISTE")
    assert vazio.atual is None and vazio.serie == [] and vazio.causas == []


def test_api_resumo_valida_filtros_e_periodos():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    padrao = client.get("/api/continuidade/resumo").json()
    assert padrao["periodo_atual"] == {"inicio": "2025-07", "fim": "2026-06"}
    assert padrao["periodo_base"] == {"inicio": "2022-07", "fim": "2023-06"}
    alimentador = MockRepository().alimentadores()[0]
    r = client.get("/api/continuidade/resumo", params={"alimentador": alimentador["id"].lower(), "comparar": "false"})
    assert r.status_code == 200 and r.json()["alimentador_id"] == alimentador["id"] and r.json()["base"] is None
    outro = next(m for m in client.get("/api/filtros").json()["municipios"] if m["nome"] != alimentador["municipio"])
    assert client.get("/api/continuidade/resumo", params={"alimentador": alimentador["id"], "municipio": outro["nome"]}).status_code == 422
    assert client.get("/api/continuidade/resumo", params={"alimentador": "XYZ"}).status_code == 422
    assert client.get("/api/continuidade/resumo", params={"municipio": "Atlântida"}).status_code == 422
    sobreposto = {"atual_inicio": "2025-07", "atual_fim": "2026-06", "base_inicio": "2025-01", "base_fim": "2025-12"}
    assert client.get("/api/continuidade/resumo", params=sobreposto).status_code == 422


def test_ranking_conta_ucs_afetadas_distintas():
    from app.services.continuidade import ranking_alimentadores
    repo = MockRepository()
    periodo = Periodo(inicio="2025-07", fim="2026-06")
    ranking = {r.alimentador_id: r for r in ranking_alimentadores(repo, periodo)}
    ocorrencias = repo.ocorrencias(periodo.inicio, periodo.fim)
    for alimentador, linha in ranking.items():
        proprias = [o for o in ocorrencias if o["alimentador_id"] == alimentador]
        assert linha.qtd_ucs_afetadas == len({o["uc_id"] for o in proprias})
        assert linha.qtd_ucs_afetadas <= linha.n_ocorrencias
