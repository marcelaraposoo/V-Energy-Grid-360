import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


CORS_PADRAO = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173"
)


@dataclass(frozen=True)
class Settings:
    # Aplicação
    app_name: str = "V-Energy Grid 360 API"

    # Dados
    data_source: str = field(
        default_factory=lambda: os.getenv(
            "DATA_SOURCE",
            "mock",
        )
    )

    sqlite_path: str = field(
        default_factory=lambda: os.getenv(
            "SQLITE_PATH",
            "data/gold.db",
        )
    )

    # CORS
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                CORS_PADRAO,
            ).split(",")
            if origin.strip()
        )
    )

    # Gemini — provider principal
    gemini_api_key: str | None = field(
        default_factory=lambda: os.getenv(
            "GEMINI_API_KEY"
        )
    )

    gemini_model: str = "gemini-3.1-flash-lite"

    # OpenRouter — contingência
    openrouter_api_key: str | None = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_API_KEY"
        )
    )

    openrouter_models: tuple[str, ...] = (
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemma-4-31b-it:free",
    )

    provider_timeout_seconds: float = 20.0



settings = Settings()