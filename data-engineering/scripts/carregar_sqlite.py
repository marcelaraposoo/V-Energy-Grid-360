#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carrega os CSVs da camada Gold (exportados pelo notebook 04_export_banco_local)
num banco SQLite local, para o backend do portal e o agente de IA.

Uso:
    python carregar_sqlite.py                                  # lê ./dados_gold, grava ./gold.db
    python carregar_sqlite.py --entrada dados_gold --saida gold.db
    python carregar_sqlite.py --sem-conferencias               # só para dados de teste

Pasta de entrada (baixada do Volume v_energy.gold.export):
    dados_gold/manifesto.json
    dados_gold/<tabela>/part-*.csv      (um ou mais arquivos por tabela)

O que o script faz:
  1. cria cada tabela com tipos explícitos (a partir do manifesto, sem adivinhar);
  2. converte campo vazio em NULL de verdade e true/false em 1/0;
  3. cria os índices só depois da carga;
  4. confere as contagens com o manifesto e algumas somas do case;
  5. só então troca o banco antigo pelo novo (se algo falhar, o banco antigo fica como estava).

O banco gerado é SÓ da Gold. Tabelas criadas pelo portal (ordens de inspeção etc.) ficam em
outro arquivo: este arquivo é recriado do zero a cada carga. Abra-o em modo leitura:
    sqlite3.connect("file:gold.db?mode=ro", uri=True)
"""
import argparse
import csv
import glob
import json
import os
import sqlite3
import sys
import time

LOTE = 50_000

# Chave única de cada tabela (vira índice UNIQUE: também prova que a chave não repete).
CHAVES = {
    "dim_uc": ["id_uc"],
    "fato_consumo_faturamento": ["id_uc", "mes_referencia"],
    "fato_atendimento": ["protocolo"],
    "receita_decomposicao": ["municipio", "bairro", "classe"],
    "fila_inspecao": ["id_uc"],
    "kpis_mensal": ["mes_referencia"],
    "fato_interrupcao": ["id_ocorrencia"],
    "dec_fec_alimentador_mensal": ["alimentador", "mes_referencia"],
    "fato_segmento_mensal": ["mes_referencia", "municipio", "bairro", "classe"],
}
# Índices extras para os filtros do portal (o Dev pode acrescentar os que precisar).
INDICES = {
    "dim_uc": [["municipio", "bairro"], ["alimentador"]],
    "fato_consumo_faturamento": [["mes_referencia"], ["municipio", "bairro"]],
    "fato_atendimento": [["id_uc"], ["mes_referencia"], ["municipio", "bairro"]],
    "receita_decomposicao": [["classe"]],
    "fila_inspecao": [["prioridade"], ["municipio", "bairro"], ["classe"]],
    "fato_interrupcao": [["id_uc"], ["alimentador", "mes_referencia"], ["mes_referencia"]],
    "dec_fec_alimentador_mensal": [["mes_referencia"], ["municipio"]],
    "fato_segmento_mensal": [["municipio", "bairro"], ["classe"]],
    "fato_troca_medidor": [["id_uc"], ["mes_troca"], ["municipio", "bairro"]],
}


def tipo_sqlite(tipo_spark):
    t = tipo_spark.lower()
    if t in ("tinyint", "smallint", "int", "bigint", "long", "boolean"):
        return "INTEGER"
    if t in ("float", "double") or t.startswith("decimal"):
        return "REAL"
    return "TEXT"          # string, date, timestamp (datas em texto ISO)


def conversor(tipo_spark):
    t = tipo_spark.lower()
    if t in ("tinyint", "smallint", "int", "bigint", "long"):
        return int
    if t == "boolean":
        def para_bool(s):
            v = s.strip().lower()
            if v == "true":
                return 1
            if v == "false":
                return 0
            raise ValueError(f"booleano inválido: {s!r}")
        return para_bool
    if t in ("float", "double") or t.startswith("decimal"):
        return float
    return lambda s: s


def falhar(msg):
    print(f"\nERRO: {msg}", file=sys.stderr)
    raise SystemExit(1)


def carregar_tabela(con, nome, info, pasta):
    colunas = info["colunas"]
    nomes = [c["nome"] for c in colunas]
    convs = [conversor(c["tipo"]) for c in colunas]

    ddl = ", ".join(f'"{c["nome"]}" {tipo_sqlite(c["tipo"])}' for c in colunas)
    con.execute(f'DROP TABLE IF EXISTS "{nome}"')
    con.execute(f'CREATE TABLE "{nome}" ({ddl})')
    insert = f'INSERT INTO "{nome}" VALUES ({",".join("?" * len(nomes))})'

    arquivos = sorted(glob.glob(os.path.join(pasta, nome, "*.csv")))
    if not arquivos:
        falhar(f"nenhum CSV em {os.path.join(pasta, nome)}")

    total = 0
    for arq in arquivos:
        with open(arq, newline="", encoding="utf-8") as f:
            leitor = csv.reader(f)
            cabecalho = next(leitor, None)
            if cabecalho != nomes:
                falhar(f"cabeçalho de {arq} difere do manifesto.\n  arquivo:   {cabecalho}\n  manifesto: {nomes}")
            lote = []
            for n_linha, campos in enumerate(leitor, start=2):
                if len(campos) != len(nomes):
                    falhar(f"{arq}, linha {n_linha}: {len(campos)} campos (esperado {len(nomes)})")
                try:
                    lote.append(tuple(None if v == "" else cv(v) for v, cv in zip(campos, convs)))
                except ValueError as e:
                    falhar(f"{arq}, linha {n_linha}: {e}")
                if len(lote) >= LOTE:
                    con.executemany(insert, lote)
                    total += len(lote)
                    lote = []
            if lote:
                con.executemany(insert, lote)
                total += len(lote)
    con.commit()

    contado = con.execute(f'SELECT COUNT(*) FROM "{nome}"').fetchone()[0]
    if contado != info["linhas"] or total != info["linhas"]:
        falhar(f"{nome}: {contado} linhas no banco, {total} lidas, {info['linhas']} no manifesto")
    print(f"  {nome}: {contado:,} linhas carregadas".replace(",", "."))


def criar_indices(con, nome, nomes_colunas):
    for chave in [CHAVES.get(nome)] if nome in CHAVES else []:
        cols = ", ".join(f'"{c}"' for c in chave)
        try:
            con.execute(f'CREATE UNIQUE INDEX "ux_{nome}_{"_".join(chave)}" ON "{nome}" ({cols})')
        except sqlite3.IntegrityError:
            falhar(f"{nome}: a chave {chave} tem valores repetidos")
    for cols in INDICES.get(nome, []):
        faltando = [c for c in cols if c not in nomes_colunas]
        if faltando:
            print(f"  aviso: índice {cols} ignorado em {nome} (colunas ausentes: {faltando})")
            continue
        lista = ", ".join(f'"{c}"' for c in cols)
        con.execute(f'CREATE INDEX "ix_{nome}_{"_".join(cols)}" ON "{nome}" ({lista})')
    if nome not in CHAVES and nome not in INDICES:
        print(f"  aviso: {nome} sem chave nem índices definidos neste script (acrescente em CHAVES/INDICES)")


def conferir(con, manifesto, com_case):
    problemas = []

    if "fato_consumo_faturamento" in manifesto and "dim_uc" in manifesto:
        n = con.execute("""SELECT COUNT(DISTINCT f.id_uc) FROM fato_consumo_faturamento f
                           LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL""").fetchone()[0]
        print(f"  UCs da fato fora da dim_uc: {n} (esperado 0)")
        if n != 0:
            problemas.append("UCs da fato fora da dim_uc")

    if com_case and "fato_consumo_faturamento" in manifesto:
        vol = dict(con.execute("""SELECT periodo_diagnostico, SUM(consumo_kwh) FROM fato_consumo_faturamento
                                  WHERE periodo_diagnostico IN ('PRIMEIRO_ANO','ULTIMOS_12M')
                                  GROUP BY periodo_diagnostico""").fetchall())
        for periodo, esperado in (("PRIMEIRO_ANO", 227_052_927), ("ULTIMOS_12M", 218_079_054)):
            obtido = vol.get(periodo)
            ok = obtido == esperado
            print(f"  volume {periodo}: {obtido} (esperado {esperado}) [{'OK' if ok else 'DIFERENTE'}]")
            if not ok:
                problemas.append(f"volume {periodo}")

    if "fato_atendimento" in manifesto and "dim_uc" in manifesto:
        n = con.execute("""SELECT COUNT(DISTINCT f.id_uc) FROM fato_atendimento f
                           LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL""").fetchone()[0]
        print(f"  UCs com chamado fora da dim_uc: {n} (esperado 0)")
        if n != 0:
            problemas.append("UCs com chamado fora da dim_uc")

    if "fila_inspecao" in manifesto and "dim_uc" in manifesto:
        n = con.execute("""SELECT COUNT(*) FROM fila_inspecao f LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL""").fetchone()[0]
        print(f"  UCs da fila de inspeção fora da dim_uc: {n} (esperado 0)")
        if n != 0:
            problemas.append("UCs da fila de inspeção fora da dim_uc")

    if com_case and "kpis_mensal" in manifesto:
        qi, qa, n_meses = con.execute("SELECT SUM(qtd_interrupcoes), SUM(qtd_atendimentos), COUNT(*) FROM kpis_mensal").fetchone()
        for nome, obtido, esperado in (("meses", n_meses, 48), ("interrupções", qi, 180_000), ("chamados", qa, 318_871)):
            ok = obtido == esperado
            print(f"  kpis_mensal, {nome}: {obtido} (esperado {esperado}) [{'OK' if ok else 'DIFERENTE'}]")
            if not ok:
                problemas.append(f"kpis_mensal, {nome}")

    if "fato_interrupcao" in manifesto and "dim_uc" in manifesto:
        n = con.execute("""SELECT COUNT(DISTINCT f.id_uc) FROM fato_interrupcao f LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL""").fetchone()[0]
        print(f"  UCs com interrupção fora da dim_uc: {n} (esperado 0)")
        if n != 0:
            problemas.append("UCs com interrupção fora da dim_uc")

    if com_case and "fato_interrupcao" in manifesto:
        n, h = con.execute("SELECT COUNT(*), SUM(duracao_min) / 60.0 FROM fato_interrupcao").fetchone()
        ok = n == 180_000 and abs(h - 356_534.8) < 1
        print(f"  fato_interrupcao: {n} ocorrências, {h:,.1f} h (esperado 180000 e 356.534,8 h) [{'OK' if ok else 'DIFERENTE'}]")
        if not ok:
            problemas.append("fato_interrupcao: ocorrências ou horas")

    if com_case and "dec_fec_alimentador_mensal" in manifesto:
        n, alim, meses = con.execute("SELECT COUNT(*), COUNT(DISTINCT alimentador), COUNT(DISTINCT mes_referencia) FROM dec_fec_alimentador_mensal").fetchone()
        ok = (n, alim, meses) == (5856, 122, 48)
        print(f"  dec_fec_alimentador_mensal: {n} linhas, {alim} alimentadores, {meses} meses (esperado 5856, 122 e 48) [{'OK' if ok else 'DIFERENTE'}]")
        if not ok:
            problemas.append("dec_fec_alimentador_mensal: grade")

    if "fato_troca_medidor" in manifesto and "dim_uc" in manifesto:
        n = con.execute("""SELECT COUNT(DISTINCT f.id_uc) FROM fato_troca_medidor f LEFT JOIN dim_uc d ON d.id_uc = f.id_uc WHERE d.id_uc IS NULL""").fetchone()[0]
        print(f"  UCs com troca de medidor fora da dim_uc: {n} (esperado 0)")
        if n != 0:
            problemas.append("UCs com troca de medidor fora da dim_uc")

    if com_case and "fato_troca_medidor" in manifesto:
        n, m0, m1 = con.execute("SELECT COUNT(*), MIN(mes_troca), MAX(mes_troca) FROM fato_troca_medidor").fetchone()
        ok = n == 6_299 and m0 >= "2025-09" and m1 <= "2026-03"
        print(f"  fato_troca_medidor: {n} trocas, de {m0} a {m1} (esperado 6299, de 2025-09 a 2026-03) [{'OK' if ok else 'DIFERENTE'}]")
        if not ok:
            problemas.append("fato_troca_medidor: trocas")

    if com_case and "fato_segmento_mensal" in manifesto:
        v = dict(con.execute("""SELECT CASE WHEN mes_referencia BETWEEN '2022-07' AND '2023-06' THEN 'p0'
                                            WHEN mes_referencia BETWEEN '2025-07' AND '2026-06' THEN 'p1' END AS p, SUM(consumo_kwh)
                                FROM fato_segmento_mensal GROUP BY 1""").fetchall())
        for periodo, esperado in (("p0", 227_052_927), ("p1", 218_079_054)):
            obtido = v.get(periodo)
            ok = obtido is not None and abs(obtido - esperado) < 0.5
            print(f"  fato_segmento_mensal, volume {periodo}: {obtido} (esperado {esperado}) [{'OK' if ok else 'DIFERENTE'}]")
            if not ok:
                problemas.append(f"fato_segmento_mensal, volume {periodo}")

    if com_case and "fato_atendimento" in manifesto:
        n = con.execute("SELECT COUNT(*) FROM fato_atendimento WHERE mes_referencia = '2025-07'").fetchone()[0]
        ok = n == 18061
        print(f"  chamados de 2025-07: {n} (esperado 18061) [{'OK' if ok else 'DIFERENTE'}]")
        if not ok:
            problemas.append("chamados de 2025-07")

    if com_case and "receita_decomposicao" in manifesto:
        v0, v1, r0, r1 = con.execute("""SELECT SUM(volume_kwh_0), SUM(volume_kwh_1), SUM(receita_0), SUM(receita_1)
                                        FROM receita_decomposicao""").fetchone()
        for nome, obtido, esperado in (("volume do primeiro ano", v0, 227_052_927), ("volume dos últimos 12 meses", v1, 218_079_054),
                                       ("receita do primeiro ano", r0, 117_830_394.38), ("receita dos últimos 12 meses", r1, 127_262_595.65)):
            ok = abs(obtido - esperado) < 0.01
            print(f"  receita_decomposicao, {nome}: {obtido:,.2f} (esperado {esperado:,.2f}) [{'OK' if ok else 'DIFERENTE'}]")
            if not ok:
                problemas.append(f"receita_decomposicao, {nome}")

    if com_case and "dim_uc" in manifesto:
        n_gd = con.execute("SELECT COUNT(*) FROM dim_uc WHERE possui_gd = 1").fetchone()[0]
        ok = n_gd == 3510
        print(f"  UCs com GD na dim_uc: {n_gd} (esperado 3510) [{'OK' if ok else 'DIFERENTE'}]")
        if not ok:
            problemas.append("UCs com GD")
    return problemas


def main():
    ap = argparse.ArgumentParser(description="Carrega os CSVs da Gold num SQLite local.")
    ap.add_argument("--entrada", default="dados_gold")
    ap.add_argument("--saida", default="gold.db")
    ap.add_argument("--sem-conferencias", action="store_true",
                    help="não confere os números do case (use só com dados de teste)")
    args = ap.parse_args()

    caminho_manifesto = os.path.join(args.entrada, "manifesto.json")
    if not os.path.exists(caminho_manifesto):
        falhar(f"{caminho_manifesto} não encontrado (baixe a pasta export do Volume do Databricks)")
    with open(caminho_manifesto, encoding="utf-8") as f:
        manifesto = json.load(f)

    tmp = args.saida + ".tmp"
    for p in (tmp, tmp + "-journal"):
        if os.path.exists(p):
            os.remove(p)

    inicio = time.time()
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode = OFF")      # banco descartável: se falhar, é recriado
    con.execute("PRAGMA synchronous = OFF")
    try:
        print(f"Carregando {len(manifesto)} tabela(s) de {args.entrada}/")
        for nome, info in manifesto.items():
            carregar_tabela(con, nome, info, args.entrada)
        print("Criando índices")
        for nome, info in manifesto.items():
            criar_indices(con, nome, [c["nome"] for c in info["colunas"]])
        con.execute("ANALYZE")
        con.commit()
        print("Conferências")
        problemas = conferir(con, manifesto, com_case=not args.sem_conferencias)
        if problemas:
            falhar("conferências falharam: " + "; ".join(problemas) + ". O banco antigo foi mantido.")
    except BaseException:
        con.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    con.close()
    os.replace(tmp, args.saida)
    mb = os.path.getsize(args.saida) / 1e6
    print(f"\nPronto: {args.saida} ({mb:,.0f} MB) em {time.time() - inicio:,.0f} s".replace(",", "."))


if __name__ == "__main__":
    main()
