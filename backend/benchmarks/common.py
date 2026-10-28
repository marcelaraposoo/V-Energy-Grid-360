import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

import asyncio
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from pydantic_ai import Agent, NativeOutput, PromptedOutput
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.agent.providers import openrouter
from app.agent.providers.gemini import classify_gemini_error
from app.agent.providers.openrouter import (
    classify_openrouter_error,
)
from app.agent.schemas import (
    SQLGenerationResult,
    SQLGenerationStatus,
)
from app.core.config import settings


BENCHMARKS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = BENCHMARKS_DIR.parent

RESULTS_DIR = BENCHMARKS_DIR / "results"

SCHEMA_PATH = (
    BACKEND_ROOT
    / "tests"
    / "fixtures"
    / "gold_schema_context_v1.md"
)

EXTRA_GEMINI_MODEL = "gemini-3.5-flash-lite"

# Candidatos fora do pool atual do OpenRouter.
EXTRA_OPENROUTER_MODELS = ("cohere/north-mini-code:free",)

# Modos do OpenRouter: "tool" foi instável nos health checks de 27/10.
OPENROUTER_MODES = ("prompted",)

# Modelos que não gastam cota: 429 em 12/12 chamadas.
EXCLUDED_OPENROUTER_MODELS = ("google/gemma-4-31b-it:free",)

OPENROUTER_PACING_SECONDS = 4.0


@dataclass(frozen=True)
class Candidate:
    label: str
    provider: str  # "gemini" | "openrouter"
    model: str
    mode: str  # "native" | "tool" | "prompted"

    @property
    def name(self) -> str:
        return f"{self.label} [{self.mode}]"


@dataclass(frozen=True)
class RunRecord:
    candidate: Candidate
    success: bool
    latency_ms: float
    error_type: str | None
    output: SQLGenerationResult | None
    detail: str = ""


def available_candidates() -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    notes: list[str] = []

    if settings.gemini_api_key:
        for model in dict.fromkeys(
            [settings.gemini_model, EXTRA_GEMINI_MODEL]
        ):
            candidates.append(
                Candidate(
                    f"gemini/{model}", "gemini", model, "native"
                )
            )
    else:
        notes.append("GEMINI_API_KEY ausente: Gemini ignorado.")

    if settings.openrouter_api_key:
        models = [
            model
            for model in dict.fromkeys(
                [
                    *settings.openrouter_models,
                    *EXTRA_OPENROUTER_MODELS,
                ]
            )
            if model not in EXCLUDED_OPENROUTER_MODELS
        ]

        for model in models:
            for mode in OPENROUTER_MODES:
                candidates.append(
                    Candidate(
                        f"openrouter/{model}",
                        "openrouter",
                        model,
                        mode,
                    )
                )
    else:
        notes.append(
            "OPENROUTER_API_KEY ausente: OpenRouter ignorado."
        )

    return candidates, notes


def _build_model(candidate: Candidate):
    if candidate.provider == "gemini":
        return GoogleModel(
            candidate.model,
            provider=GoogleProvider(
                api_key=settings.gemini_api_key
            ),
        )

    return openrouter._build_model(candidate.model)


def _output_type(mode: str):
    if mode == "native":
        return NativeOutput(SQLGenerationResult)

    if mode == "prompted":
        return PromptedOutput(SQLGenerationResult)

    # "tool": modo padrão do PydanticAI, o mesmo que o
    # openrouter.py usa hoje.
    return SQLGenerationResult


def _classify(candidate: Candidate, error: Exception) -> str:
    if isinstance(error, UserError):
        return "unsupported_mode"

    if candidate.provider == "gemini":
        return classify_gemini_error(error).value

    return classify_openrouter_error(error).value


async def run_candidate(
    candidate: Candidate,
    prompt: str,
    instructions: str,
) -> RunRecord:
    started = perf_counter()

    try:
        agent = Agent(
            model=_build_model(candidate),
            retries={"tools": 0, "output": 0},
            model_settings={
                "max_retries": 0,
                "request_timeout": (
                    settings.provider_timeout_seconds
                ),
                "temperature": 0,
            },
        )

        result = await agent.run(
            prompt,
            instructions=instructions,
            output_type=_output_type(candidate.mode),
        )

        return RunRecord(
            candidate=candidate,
            success=True,
            latency_ms=(perf_counter() - started) * 1000,
            error_type=None,
            output=result.output,
        )

    except Exception as error:
        return RunRecord(
            candidate=candidate,
            success=False,
            latency_ms=(perf_counter() - started) * 1000,
            error_type=_classify(candidate, error),
            output=None,
            detail=(
                f"{type(error).__name__}: "
                f"{str(error)[:160]}"
            ),
        )


async def pace(candidate: Candidate) -> None:
    if candidate.provider == "openrouter":
        await asyncio.sleep(OPENROUTER_PACING_SECONDS)


def summarize(records: list[RunRecord]) -> list[tuple]:
    grouped: dict[str, list[RunRecord]] = {}

    for record in records:
        grouped.setdefault(record.candidate.name, []).append(
            record
        )

    rows = []

    for name, items in grouped.items():
        ok = [r for r in items if r.success]
        ready = [
            r
            for r in ok
            if r.output
            and r.output.status == SQLGenerationStatus.READY
        ]
        latencies = [r.latency_ms for r in ok]
        errors = Counter(
            r.error_type for r in items if not r.success
        )

        rows.append(
            (
                name,
                len(ok),
                len(items),
                len(ready),
                statistics.median(latencies)
                if latencies
                else None,
                dict(errors),
            )
        )

    return rows


def format_summary_table(rows: list[tuple]) -> str:
    lines = [
        "| Modelo [modo] | Saída válida | READY | "
        "Latência mediana (ms) | Erros |",
        "|---|---|---|---|---|",
    ]

    for name, ok, total, ready, median, errors in rows:
        latency = f"{median:.0f}" if median is not None else "-"
        error_text = (
            ", ".join(f"{k}×{v}" for k, v in errors.items())
            or "-"
        )

        lines.append(
            f"| {name} | {ok}/{total} | {ready}/{total} | "
            f"{latency} | {error_text} |"
        )

    return "\n".join(lines)