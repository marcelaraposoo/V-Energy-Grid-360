import argparse
import asyncio
from datetime import datetime

from benchmarks.common import (
    RESULTS_DIR,
    SCHEMA_PATH,
    available_candidates,
    format_summary_table,
    pace,
    run_candidate,
    summarize,
)
from app.agent.prompts.sql_generation.loader import (
    load_sql_generation_prompts,
)
from app.agent.sql_generator import build_sql_generation_prompt


QUESTION = "Quantas contas de luz estão em aberto em 2026-06?"


def _clean(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


async def main(repeats: int) -> None:
    context = SCHEMA_PATH.read_text(encoding="utf-8").strip()

    prompt = build_sql_generation_prompt(
        question=QUESTION,
        database_context=context,
    )
    instructions = load_sql_generation_prompts()

    candidates, notes = available_candidates()

    for note in notes:
        print(note)

    records = []

    # Rodadas externas: cada modelo é chamado de novo só depois
    # dos outros, o que espalha as chamadas no tempo.
    for round_number in range(1, repeats + 1):
        for candidate in candidates:
            record = await run_candidate(
                candidate, prompt, instructions
            )
            records.append((round_number, record))

            status = "OK  " if record.success else "FAIL"
            print(
                f"[{round_number}/{repeats}] {status} "
                f"{candidate.name} | "
                f"{record.latency_ms:.0f} ms | "
                f"erro={record.error_type}"
            )

            await pace(candidate)

    summary = format_summary_table(
        summarize([record for _, record in records])
    )

    print("\n" + summary)

    RESULTS_DIR.mkdir(exist_ok=True)

    moment = datetime.now()
    path = RESULTS_DIR / (
        f"health_{moment.strftime('%Y-%m-%d_%H%M')}.md"
    )

    raw_lines = [
        "| Rodada | Modelo [modo] | OK | Latência (ms) | "
        "Erro | Detalhe |",
        "|---|---|---|---|---|---|",
    ]

    for round_number, record in records:
        raw_lines.append(
            f"| {round_number} | {record.candidate.name} | "
            f"{'sim' if record.success else 'não'} | "
            f"{record.latency_ms:.0f} | "
            f"{record.error_type or '-'} | "
            f"{_clean(record.detail) or '-'} |"
        )

    path.write_text(
        "# Saúde dos modelos de fallback\n\n"
        f"Executado em {moment.strftime('%d/%m/%Y %H:%M')}.\n\n"
        f"Pergunta: {QUESTION}\n\n"
        "Cada chamada usa o prompt real da etapa 4.1 com o "
        "esquema Gold v1 e temperatura 0.\n\n"
        "## Resumo\n\n"
        f"{summary}\n\n"
        "## Chamadas\n\n"
        + "\n".join(raw_lines)
        + "\n",
        encoding="utf-8",
    )

    print(f"\nResultado salvo em: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=2)

    arguments = parser.parse_args()

    asyncio.run(main(arguments.repeats))