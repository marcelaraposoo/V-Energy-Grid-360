#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mostra o que há dentro de um gold.db, sem programa nenhum além do Python.
Abre o banco só para leitura (não altera nada).

Uso:
    python conferir_sqlite.py gold.db
    python conferir_sqlite.py gold.db --uc UC100086      # visão 360 de uma UC
    python conferir_sqlite.py gold.db --linhas 5         # mais linhas de exemplo

Mostra, para cada tabela: linhas, colunas com o tipo, colunas que têm nulos, as primeiras linhas e os índices;
depois os números do case (volumes, UCs com GD, chamados de julho de 2025) e a visão 360 de uma UC.
"""
import argparse
import sqlite3
import sys


def existentes(con, tabela, desejadas):
    cols = {r[1] for r in con.execute(f'PRAGMA table_info("{tabela}")')}
    return [c for c in desejadas if c in cols]


def tabelas(con):
    return [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def mostrar(con, sql, params=(), titulo=None):
    cur = con.execute(sql, params)
    linhas = cur.fetchall()
    if titulo:
        print(titulo)
    if not linhas:
        print("   (nenhuma linha)")
        return
    nomes = [d[0] for d in cur.description]
    larg = [max(len(str(n)), *(len(str(l[i])) for l in linhas)) for i, n in enumerate(nomes)]
    print("   " + " | ".join(str(n).ljust(larg[i]) for i, n in enumerate(nomes)))
    for l in linhas:
        print("   " + " | ".join(str("" if v is None else v).ljust(larg[i]) for i, v in enumerate(l)))


def main():
    ap = argparse.ArgumentParser(description="Mostra o conteúdo de um gold.db (só leitura).")
    ap.add_argument("db")
    ap.add_argument("--uc", default=None, help="id_uc para a visão 360 (padrão: a primeira da dim_uc)")
    ap.add_argument("--linhas", type=int, default=2, help="linhas de exemplo por tabela")
    args = ap.parse_args()

    try:
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        ts = tabelas(con)
    except sqlite3.Error as e:
        sys.exit(f"não consegui abrir {args.db}: {e}")
    print(f"banco: {args.db} | {len(ts)} tabela(s): {', '.join(ts)}")

    # 1. cada tabela
    for t in ts:
        n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        cols = con.execute(f'PRAGMA table_info("{t}")').fetchall()
        print(f"\n=== {t}: {n:,}".replace(",", ".") + f" linhas, {len(cols)} colunas")
        print("   colunas: " + ", ".join(f"{c[1]} ({c[2]})" for c in cols))
        nulos = con.execute("SELECT " + ", ".join(f'SUM("{c[1]}" IS NULL)' for c in cols) + f' FROM "{t}"').fetchone()
        com_nulo = [(c[1], int(v)) for c, v in zip(cols, nulos) if v]
        print("   colunas com nulos: " + (", ".join(f"{c} ({v:,})".replace(",", ".") for c, v in com_nulo) if com_nulo else "nenhuma"))
        print("   índices: " + (", ".join(r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? AND name NOT LIKE 'sqlite_%'", (t,))) or "nenhum"))
        for k, linha in enumerate(con.execute(f'SELECT * FROM "{t}" LIMIT ?', (args.linhas,)).fetchall(), 1):
            print(f"   exemplo {k}: " + "; ".join(f"{c[1]}={'' if v is None else v}" for c, v in zip(cols, linha)))

    # 2. números do case
    print("\n=== números do case")
    if "fato_consumo_faturamento" in ts and "periodo_diagnostico" in existentes(con, "fato_consumo_faturamento", ["periodo_diagnostico"]):
        mostrar(con, """SELECT periodo_diagnostico, SUM(consumo_kwh) AS volume_kwh, ROUND(SUM(valor_energia), 2) AS receita_energia,
                               COUNT(DISTINCT id_uc) AS ucs FROM fato_consumo_faturamento
                        WHERE periodo_diagnostico <> 'OUTRO' GROUP BY 1 ORDER BY 1""",
                titulo="  volume e receita por período (esperado: 227.052.927 e 218.079.054 kWh; R$ 117.830.394,38 e R$ 127.262.595,65; 44.741 e 45.000 UCs)")
    if "dim_uc" in ts and existentes(con, "dim_uc", ["possui_gd"]):
        print("  UCs com GD na dim_uc:", con.execute("SELECT COUNT(*) FROM dim_uc WHERE possui_gd = 1").fetchone()[0], "(esperado 3510 no banco completo)")
    if "fato_atendimento" in ts:
        print("  chamados de 2025-07:", con.execute("SELECT COUNT(*) FROM fato_atendimento WHERE mes_referencia = '2025-07'").fetchone()[0], "(esperado 18061 no banco completo)")
    if "fato_consumo_faturamento" in ts and "dim_uc" in ts:
        print("  UCs da fato fora da dim_uc:", con.execute("SELECT COUNT(DISTINCT f.id_uc) FROM fato_consumo_faturamento f LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL").fetchone()[0], "(esperado 0)")

    # 3. visão 360 de uma UC
    if "dim_uc" in ts:
        uc = args.uc or con.execute("SELECT id_uc FROM dim_uc ORDER BY id_uc LIMIT 1").fetchone()[0]
        print(f"\n=== visão 360 da UC {uc}")
        c = existentes(con, "dim_uc", ["id_uc", "nome_titular_mascarado", "municipio", "bairro", "classe", "possui_gd", "tipo_medidor_ativo", "idade_medidor_anos"])
        mostrar(con, f'SELECT {", ".join(c)} FROM dim_uc WHERE id_uc = ?', (uc,), titulo="  cadastro:")
        if "fato_consumo_faturamento" in ts:
            c = existentes(con, "fato_consumo_faturamento", ["mes_referencia", "consumo_kwh", "consumo_kwh_ano_anterior",
                                                             "variacao_consumo_ano_anterior_pct", "valor_total", "status_fatura", "dias_atraso", "faixa_atraso"])
            mostrar(con, f'SELECT {", ".join(c)} FROM fato_consumo_faturamento WHERE id_uc = ? ORDER BY mes_referencia DESC LIMIT 6', (uc,),
                    titulo="  últimos 6 meses (consumo, mesmo mês do ano anterior e fatura):")
            if "em_aberto" in existentes(con, "fato_consumo_faturamento", ["em_aberto"]):
                mostrar(con, "SELECT faixa_atraso, COUNT(*) AS faturas, ROUND(SUM(valor_total), 2) AS valor FROM fato_consumo_faturamento WHERE id_uc = ? AND em_aberto = 1 GROUP BY 1 ORDER BY 1",
                        (uc,), titulo="  faturas em aberto, por faixa de atraso:")
        if "fato_atendimento" in ts:
            c = existentes(con, "fato_atendimento", ["protocolo", "data_hora_abertura", "assunto", "tempo_resolucao_horas", "nota_satisfacao"])
            mostrar(con, f'SELECT {", ".join(c)} FROM fato_atendimento WHERE id_uc = ? ORDER BY data_hora_abertura DESC LIMIT 5', (uc,),
                    titulo="  últimos chamados:")
    con.close()


if __name__ == "__main__":
    main()
