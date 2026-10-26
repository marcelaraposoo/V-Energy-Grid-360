from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent

PROMPT_FILES = (
    "system.md",
    "domain.md",
    "security.md",
    "sql_rules.md",
    "output_contract.md",
)


def _load_prompt_file(filename: str) -> str:
    path = PROMPTS_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de prompt não encontrado: {path}"
        )

    content = path.read_text(
        encoding="utf-8"
    ).strip()

    if not content:
        raise ValueError(
            f"Arquivo de prompt vazio: {path}"
        )

    return content


def load_sql_generation_prompts() -> str:
    prompts = [
        _load_prompt_file(filename)
        for filename in PROMPT_FILES
    ]

    return "\n\n".join(prompts)