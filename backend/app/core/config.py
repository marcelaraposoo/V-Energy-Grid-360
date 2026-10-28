import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BACKEND_DIR / ".env")


def _caminho_no_backend(valor: str) -> str:
    """Caminho relativo vale a partir da pasta backend (e não de onde o uvicorn foi iniciado),
    para não nascer um segundo banco vazio ao rodar de outra pasta."""
    if valor == ":memory:" or Path(valor).is_absolute():
        return valor
    return str(BACKEND_DIR / valor)


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

    # Banco do portal (ordens de inspeção): separado do gold.db para a exportação da Gold não apagá-lo
    portal_db_path: str = field(
        default_factory=lambda: _caminho_no_backend(
            os.getenv(
                "PORTAL_DB_PATH",
                "data/portal.db",
            )
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

    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_last_resort_model: str | None = "gemini-3.1-flash-lite"

    # OpenRouter — contingência
    openrouter_api_key: str | None = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_API_KEY"
        )
    )

    openrouter_models = (
        "cohere/north-mini-code:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    )

    provider_timeout_seconds: float = 30.0



settings = Settings()