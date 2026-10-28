import json
from collections import Counter, defaultdict

from benchmarks.common import RESULTS_DIR


RUNS_PATH = RESULTS_DIR / "benchmark_runs.jsonl"


def main() -> None:
    attempts = defaultdict(list)

    for line in RUNS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            attempts[record["candidate"]].append(record)

    rows = []

    for name, items in attempts.items():
        ok = sum(1 for r in items if r["success"])
        errors = Counter(
            r["error_type"] for r in items if not r["success"]
        )
        rows.append((name, len(items), ok, errors))

    rows.sort(key=lambda row: -row[2] / row[1])

    print(
        "| Modelo | Tentativas | Responderam | Disponibilidade | Falhas |"
    )
    print("|---|---|---|---|---|")

    for name, total, ok, errors in rows:
        error_text = (
            ", ".join(f"{k}×{v}" for k, v in errors.items()) or "-"
        )

        print(
            f"| {name} | {total} | {ok} | {ok / total:.0%} | "
            f"{error_text} |"
        )


if __name__ == "__main__":
    main()