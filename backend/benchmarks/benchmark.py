import argparse
import asyncio
import json
import sqlite3
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import time

from benchmarks.build_synthetic_db import DB_PATH
from benchmarks.common import (
    RESULTS_DIR,
    SCHEMA_PATH,
    available_candidates,
    pace,
    run_candidate,
)
from benchmarks.questions import QUESTIONS
from app.agent.guardrails.sql_guardrail import validate_sql
from app.agent.prompts.sql_generation.loader import (
    load_sql_generation_prompts,
)
from app.agent.schemas import (
    SQLGenerationStatus,
    SQLGuardrailDecision,
)
from app.agent.sql_generator import build_sql_generation_prompt


RUNS_PATH = RESULTS_DIR / "benchmark_runs.jsonl"
REPORT_PATH = RESULTS_DIR / "benchmark_report.md"

# Erros de infraestrutura são repetidos na próxima execução;
# os demais (ex.: invalid_output) contam como resultado do modelo.
TRANSIENT_ERRORS = {
    "rate_limited",
    "timeout",
    "provider_unavailable",
    "connection_error",
    "quota_exhausted",
}

MAX_ROWS = 1000
SQL_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------
# Banco e comparação de resultados
# ---------------------------------------------------------------

def open_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(
            f"Banco não encontrado: {path}\n"
            "Rode: python -m benchmarks.build_synthetic_db"
        )

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA query_only = ON")

    return conn


def run_sql(conn, sql: str):
    deadline = time() + SQL_TIMEOUT_SECONDS
    conn.set_progress_handler(
        lambda: 1 if time() > deadline else 0, 100_000
    )

    try:
        rows = conn.execute(sql).fetchmany(MAX_ROWS)

        return [list(row) for row in rows], None
    except Exception as error:
        return None, f"{type(error).__name__}: {str(error)[:150]}"
    finally:
        conn.set_progress_handler(None, 0)


def _norm(value) -> str:
    if value is None:
        return "NULL"

    if isinstance(value, (bool, int, float)):
        return f"{round(float(value), 2) + 0.0:.2f}"

    return str(value).strip().lower()


def _contains(model_row: Counter, ref_row: Counter) -> bool:
    return all(model_row[k] >= v for k, v in ref_row.items())


def compare_results(ref_rows, model_rows, ordered: bool) -> str:
    """
    'exact': mesmas linhas e valores (ordem das colunas livre).
    'superset': cada linha da referência está contida em uma
    linha do modelo (colunas a mais, como um nome ou um ranking).
    'mismatch': qualquer outra situação.
    """

    if len(ref_rows) != len(model_rows):
        return "mismatch"

    ref = [Counter(_norm(v) for v in row) for row in ref_rows]
    model = [Counter(_norm(v) for v in row) for row in model_rows]

    all_equal = True

    if ordered:
        pairs = list(zip(ref, model))

        if not all(_contains(m, r) for r, m in pairs):
            return "mismatch"

        all_equal = all(m == r for r, m in pairs)
    else:
        pool = list(model)

        for ref_row in ref:
            index = next(
                (i for i, m in enumerate(pool) if m == ref_row),
                None,
            )

            if index is None:
                all_equal = False
                index = next(
                    (
                        i
                        for i, m in enumerate(pool)
                        if _contains(m, ref_row)
                    ),
                    None,
                )

            if index is None:
                return "mismatch"

            pool.pop(index)

    return "exact" if all_equal else "superset"


# ---------------------------------------------------------------
# Persistência (permite retomar em outro dia)
# ---------------------------------------------------------------

def load_runs() -> dict:
    runs = {}

    if RUNS_PATH.exists():
        for line in RUNS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                runs[(record["question_id"], record["candidate"])] = record

    return runs


def append_run(record: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)

    with RUNS_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def is_done(record) -> bool:
    return record is not None and (
        record["success"]
        or record["error_type"] not in TRANSIENT_ERRORS
    )


# ---------------------------------------------------------------
# Avaliação de uma chamada
# ---------------------------------------------------------------

def evaluate(question, record, conn, ref_rows) -> dict:
    result = {
        "question_id": question.id,
        "category": question.category,
        "candidate": record.candidate.name,
        "success": record.success,
        "error_type": record.error_type,
        "detail": record.detail,
        "latency_ms": round(record.latency_ms),
        "status": None,
        "sql": None,
        "reason": None,
        "guardrail": None,
        "executed": None,
        "exec_error": None,
        "match": None,
        "at": datetime.now().isoformat(timespec="seconds"),
    }

    if not record.success:
        return result

    output = record.output
    result["status"] = output.status.value
    result["sql"] = output.sql
    result["reason"] = output.reason

    if output.status != SQLGenerationStatus.READY or not output.sql:
        return result

    guardrail = validate_sql(output.sql)

    if guardrail.decision != SQLGuardrailDecision.ALLOW:
        result["guardrail"] = f"block:{guardrail.reason.value}"

        return result

    result["guardrail"] = "allow"

    rows, error = run_sql(conn, output.sql)
    result["executed"] = error is None
    result["exec_error"] = error

    if (
        error is None
        and question.expected == "ready"
        and ref_rows is not None
    ):
        result["match"] = compare_results(
            ref_rows, rows, question.ordered
        )

    return result


# ---------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------

def _symbol(question, record) -> str:
    if record is None:
        return "·"

    if not record["success"]:
        return "—"

    if question.expected == "ready":
        if record["status"] != "ready":
            return "⛔"

        return {"exact": "✓", "superset": "≈"}.get(
            record["match"], "✗"
        )

    if record["status"] == question.expected:
        return "✓"

    return "✗" if record["status"] == "ready" else "~"


def build_report(runs: dict) -> str:
    questions = {q.id: q for q in QUESTIONS}
    n_ready = sum(1 for q in QUESTIONS if q.expected == "ready")
    n_other = len(QUESTIONS) - n_ready

    by_candidate: dict[str, list] = {}

    for (_, name), record in runs.items():
        by_candidate.setdefault(name, []).append(record)

    rows = []

    for name, items in by_candidate.items():
        ok = [r for r in items if r["success"]]
        ready = [
            r for r in items
            if questions[r["question_id"]].expected == "ready"
        ]
        other = [
            r for r in items
            if questions[r["question_id"]].expected != "ready"
        ]

        matched = sum(
            1 for r in ready if r["match"] in ("exact", "superset")
        )
        exact = sum(1 for r in ready if r["match"] == "exact")
        executes = sum(1 for r in ready if r["executed"])
        correct_status = sum(
            1 for r in ok
            if r["status"] == questions[r["question_id"]].expected
        )
        safe = sum(
            1 for r in other if r["success"] and r["status"] != "ready"
        )
        latencies = [r["latency_ms"] for r in ok]
        errors = Counter(
            r["error_type"] for r in items if not r["success"]
        )

        rows.append(
            (
                name, len(items), len(ok), correct_status,
                matched, exact, executes, safe,
                statistics.median(latencies) if latencies else None,
                dict(errors),
            )
        )

    rows.sort(key=lambda r: (-r[4], r[8] if r[8] is not None else 1e9))

    total = len(QUESTIONS)
    lines = [
        "| Modelo | Chamadas | Saída válida | Classificação certa | "
        f"Resultado igual (de {n_ready}) | Exato | SQL executa | "
        f"Barrou ataque/fora (de {n_other}) | Latência mediana (ms) | "
        "Erros |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for (name, n, ok, cls, match, exact, run, safe, med, errs) in rows:
        error_text = (
            ", ".join(f"{k}×{v}" for k, v in errs.items()) or "-"
        )

        lines.append(
            f"| {name} | {n}/{total} | {ok}/{n} | {cls}/{n} | "
            f"{match}/{n_ready} | {exact} | {run} | {safe}/{n_other} | "
            f"{f'{med:.0f}' if med is not None else '-'} | "
            f"{error_text} |"
        )

    names = [row[0] for row in rows]
    matrix = [
        "| Pergunta | Tipo | " + " | ".join(names) + " |",
        "|---|---|" + "---|" * len(names),
    ]

    for q in QUESTIONS:
        cells = [
            _symbol(q, runs.get((q.id, name))) for name in names
        ]
        matrix.append(
            f"| {q.id} | {q.category} | " + " | ".join(cells) + " |"
        )

    return (
        "# Benchmark de modelos (etapa 4.1: geração de SQL)\n\n"
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}.\n\n"
        "Banco sintético no esquema Gold v1, prompt real da 4.1, "
        "temperatura 0. 'Resultado igual' compara o resultado da "
        "execução do SQL com o de uma referência escrita à mão.\n\n"
        "## Resumo\n\n" + "\n".join(lines) + "\n\n"
        "## Por pergunta\n\n" + "\n".join(matrix) + "\n\n"
        "Legenda: ✓ certo, ≈ certo com colunas a mais, ✗ errado "
        "(resultado diferente, SQL inválido ou gerou SQL onde não "
        "devia), ⛔ classificou como não-pronto uma pergunta "
        "respondível, ~ não gerou SQL mas com outro status, "
        "— chamada falhou, · pendente.\n"
    )


# ---------------------------------------------------------------
# Execução
# ---------------------------------------------------------------

def reference_rows_by_question(conn) -> dict:
    refs = {}

    for q in QUESTIONS:
        if q.reference_sql:
            rows, error = run_sql(conn, q.reference_sql)

            if error:
                raise SystemExit(
                    f"Referência {q.id} falhou: {error}"
                )

            refs[q.id] = rows

    return refs


def check_reference(conn) -> None:
    print("Resultados das referências (confira se fazem sentido):\n")

    for q in QUESTIONS:
        if not q.reference_sql:
            continue

        rows, error = run_sql(conn, q.reference_sql)

        if error:
            print(f"{q.id}: ERRO {error}")
            continue

        flat = [v for row in rows for v in row]
        warning = ""

        if not rows:
            warning = "  <-- VAZIO"
        elif all(v in (None, 0, 0.0) for v in flat):
            warning = "  <-- SÓ ZERO/NULO"

        print(f"{q.id}: {len(rows)} linha(s) | {rows[:3]}{warning}")


async def run_benchmark(arguments) -> None:
    conn = open_db(arguments.db)
    refs = reference_rows_by_question(conn)

    candidates, notes = available_candidates()

    for note in notes:
        print(note)

    context = SCHEMA_PATH.read_text(encoding="utf-8").strip()
    instructions = load_sql_generation_prompts()

    if arguments.fresh and RUNS_PATH.exists():
        RUNS_PATH.unlink()

    runs = load_runs()
    if arguments.redo:
        redo_ids = set(arguments.redo.split(","))
        runs = {
            key: record
            for key, record in runs.items()
            if key[0] not in redo_ids
        }
        RESULTS_DIR.mkdir(exist_ok=True)
        RUNS_PATH.write_text(
            "".join(
                json.dumps(record, ensure_ascii=False) + "\n"
                for record in runs.values()
            ),
            encoding="utf-8",
        )

    only = (
        set(arguments.only.split(",")) if arguments.only else None
    )

    openrouter_calls = 0
    skipped_for_cap = 0

    for q in QUESTIONS:
        if only and q.id not in only:
            continue

        prompt = build_sql_generation_prompt(
            question=q.text, database_context=context
        )

        for candidate in candidates:
            if is_done(runs.get((q.id, candidate.name))):
                continue

            if (
                candidate.provider == "openrouter"
                and openrouter_calls >= arguments.max_openrouter_calls
            ):
                skipped_for_cap += 1
                continue

            record = await run_candidate(
                candidate, prompt, instructions
            )

            if candidate.provider == "openrouter":
                openrouter_calls += 1

            result = evaluate(q, record, conn, refs.get(q.id))
            runs[(q.id, candidate.name)] = result
            append_run(result)

            print(
                f"{q.id} {candidate.name}: "
                f"{result['status'] or result['error_type']} | "
                f"match={result['match'] or '-'} | "
                f"{result['latency_ms']} ms"
            )

            await pace(candidate)

    pending = sum(
        1
        for q in QUESTIONS
        for c in candidates
        if not is_done(runs.get((q.id, c.name)))
    )

    if pending:
        print(
            f"\n{pending} chamada(s) pendente(s) (limite de cota ou "
            "erro transitório). Rode de novo mais tarde: o script "
            "retoma de onde parou."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--check-reference", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--redo", type=str, default=None)
    parser.add_argument(
        "--max-openrouter-calls", type=int, default=45
    )

    arguments = parser.parse_args()

    if arguments.check_reference:
        check_reference(open_db(arguments.db))

        return

    if not arguments.report_only:
        asyncio.run(run_benchmark(arguments))

    RESULTS_DIR.mkdir(exist_ok=True)

    report = build_report(load_runs())
    REPORT_PATH.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"Relatório salvo em: {REPORT_PATH}")


if __name__ == "__main__":
    main()