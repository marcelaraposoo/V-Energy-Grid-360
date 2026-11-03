"""Conferência da Análise de Receita contra o gold.db real (não roda na suíte: o banco não está no repositório).

Na pasta backend: python -m tests.manual.validar_receita_gold [caminho do gold.db]
Sem caminho, usa SQLITE_PATH do .env. Só lê o banco; sai com código 1 se alguma conferência falhar.

1. A3 (fato_segmento_mensal) x A2 (fato_consumo_faturamento): volume e receita de cada mês.
2. Recorte do diagnóstico: totais da tela x docs/diagnostico_receita.md.
3. GD nas mesmas UCs (A2): resultado e tempo da consulta, para decidir se precisa de cache.
"""
import sqlite3
import sys
import time

from app.core.config import settings
from app.repositories.sqlite_repo import SqliteRepository
from app.schemas import Filtros
from app.services import receita

# docs/diagnostico_receita.md (v2), seção 2, e contrato da Gold v4 (3.510 UCs com GD).
ESPERADO = {"variacao_energia_pct": -3.95, "variacao_receita_pct": 8.00, "qtd_ucs_com_gd": 3510}
TOLERANCIA_PCT = 0.01
TOLERANCIA_VALOR = 0.01


def conferir_a3_x_a2(caminho: str) -> bool:
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    a3 = {m: (q, r) for m, q, r in con.execute(
        "SELECT mes_referencia, SUM(consumo_kwh), SUM(receita_energia) FROM fato_segmento_mensal GROUP BY 1")}
    a2 = {m: (q, r) for m, q, r in con.execute(
        "SELECT mes_referencia, SUM(consumo_kwh), SUM(valor_energia) FROM fato_consumo_faturamento GROUP BY 1")}
    con.close()
    divergentes = [
        (mes, a3.get(mes), a2.get(mes)) for mes in sorted(set(a3) | set(a2))
        if mes not in a3 or mes not in a2
        or any(abs((x or 0) - (y or 0)) > TOLERANCIA_VALOR for x, y in zip(a3[mes], a2[mes]))
    ]
    print(f"[1] A3 x A2: {len(set(a3) | set(a2))} competências, {len(divergentes)} divergentes")
    for mes, v3, v2 in divergentes[:10]:
        print(f"    {mes}: A3 (kWh, R$) = {v3} | A2 = {v2}")
    return not divergentes


def conferir_diagnostico(repo: SqliteRepository) -> bool:
    base, atual = receita.PERIODOS_DIAGNOSTICO
    inicio = time.perf_counter()
    v = receita.variacao(repo, base, atual, Filtros(), "municipio")
    duracao = time.perf_counter() - inicio
    t, f = v.total, v.fatores
    obtido = {"variacao_energia_pct": t.variacao_energia_pct, "variacao_receita_pct": t.variacao_receita_pct, "qtd_ucs_com_gd": f.qtd_ucs_com_gd}
    ok = all(
        obtido[k] is not None and abs(obtido[k] - esperado) <= (TOLERANCIA_PCT if k.endswith("_pct") else 0)
        for k, esperado in ESPERADO.items()
    )
    print(f"[2] Diagnóstico: {'OK' if ok else 'DIVERGENTE'} (resposta completa em {duracao:.2f} s)")
    for k, esperado in ESPERADO.items():
        print(f"    {k}: esperado {esperado} | obtido {obtido[k]}")
    print(f"    efeito volume R$ {t.efeito_volume:,.2f} | efeito preço R$ {t.efeito_preco:,.2f} | variação R$ {t.variacao_receita:,.2f}")
    return ok


def medir_gd(repo: SqliteRepository) -> None:
    base, atual = receita.PERIODOS_DIAGNOSTICO
    inicio = time.perf_counter()
    gd = repo.gd_mesmas_ucs(base.inicio, base.fim, atual.inicio, atual.fim)
    duracao = time.perf_counter() - inicio
    if gd is None:
        print("[3] GD: fato_consumo_faturamento não exportada (volumes de GD ficarão nulos)")
        return
    queda = (gd["energia_atual_kwh"] / gd["energia_base_kwh"] - 1) * 100 if gd["energia_base_kwh"] else None
    print(f"[3] GD: {gd['qtd_ucs']} UCs, {gd['energia_base_kwh']:,.0f} → {gd['energia_atual_kwh']:,.0f} kWh"
          f" ({queda:+.1f}%; diagnóstico: −61%) em {duracao:.2f} s" if queda is not None else f"[3] GD: {gd} em {duracao:.2f} s")


def main(caminho: str) -> int:
    repo = SqliteRepository(caminho)
    ok = conferir_a3_x_a2(caminho)
    ok = conferir_diagnostico(repo) and ok
    medir_gd(repo)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else settings.sqlite_path))
