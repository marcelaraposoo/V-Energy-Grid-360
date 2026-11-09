import os
import math
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from app.agent.state.cache import (
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_CACHE_TIMEOUT_SECONDS,
    validate_cache_ttl,
    validate_cache_timeout,
)
from app.agent.state.cache_key import has_data_version
from app.agent.state.memory import DEFAULT_MEMORY_TTL_SECONDS, DEFAULT_MEMORY_TIMEOUT_SECONDS


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


def _provider_seconds(name: str, default: str) -> float:
    value = float(os.getenv(name, default))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} deve ser positivo e finito.")
    return value


@dataclass(frozen=True)
class Settings:
    # Aplicação
    app_name: str = "V-Energy Grid 360 API"

    # Observabilidade: opt-in explícito; token nunca aparece no repr das settings.
    logfire_enabled: bool = field(
        default_factory=lambda: os.getenv("LOGFIRE_ENABLED", "false").strip().lower() in {"1", "true"}
    )
    logfire_token: str | None = field(
        default_factory=lambda: os.getenv("LOGFIRE_TOKEN", "").strip() or None, repr=False
    )
    logfire_service_name: str = field(
        default_factory=lambda: os.getenv("LOGFIRE_SERVICE_NAME", "v-energy-grid-360-backend")
    )
    logfire_base_url: str | None = field(
        default_factory=lambda: os.getenv("LOGFIRE_BASE_URL", "").strip() or None
    )

    # C2: sem URL, o agente funciona sem cache. Snapshot explícito se habilitado.
    redis_url: str | None = field(
        default_factory=lambda: os.getenv("REDIS_URL", "").strip() or None
    )
    gold_data_version: str | None = field(
        default_factory=lambda: os.getenv("GOLD_DATA_VERSION")
    )
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS)))
    )
    cache_max_entries_per_session: int = field(
        default_factory=lambda: int(os.getenv("CACHE_MAX_ENTRIES_PER_SESSION", "100"))
    )
    cache_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("CACHE_TIMEOUT_SECONDS", str(DEFAULT_CACHE_TIMEOUT_SECONDS)))
    )
    memory_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("MEMORY_TTL_SECONDS", str(DEFAULT_MEMORY_TTL_SECONDS)))
    )
    memory_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("MEMORY_TIMEOUT_SECONDS", str(DEFAULT_MEMORY_TIMEOUT_SECONDS)))
    )

    def __post_init__(self) -> None:
        if self.redis_url:
            if not has_data_version(self.gold_data_version):
                raise ValueError("GOLD_DATA_VERSION é obrigatória com REDIS_URL configurada.")
            validate_cache_ttl(self.cache_ttl_seconds)
            validate_cache_ttl(self.cache_max_entries_per_session)
            validate_cache_timeout(self.cache_timeout_seconds)
            validate_cache_ttl(self.memory_ttl_seconds)
            validate_cache_timeout(self.memory_timeout_seconds)

    # Dados
    data_source: str = field(
        default_factory=lambda: os.getenv(
            "DATA_SOURCE",
            "mock",
        )
    )

    sqlite_path: str = field(
        default_factory=lambda: _caminho_no_backend(
            os.getenv(
                "SQLITE_PATH",
                "data/gold.db",
            )
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

    # Somente payload inteiramente sintético pode liberar endpoints restritos.
    provider_payload_policy: str = field(
        default_factory=lambda: os.getenv("PROVIDER_PAYLOAD_POLICY", "confidential")
    )

    provider_timeout_seconds: float = field(
        default_factory=lambda: _provider_seconds("PROVIDER_TIMEOUT_SECONDS", "20")
    )
    provider_primary_timeout_seconds: float = field(
        default_factory=lambda: _provider_seconds("PROVIDER_PRIMARY_TIMEOUT_SECONDS", "8")
    )
    provider_reuse_success: bool = field(
        default_factory=lambda: os.getenv("PROVIDER_REUSE_SUCCESS", "true").lower() == "true"
    )
    provider_phase_budgets_enabled: bool = field(
        default_factory=lambda: os.getenv("PROVIDER_PHASE_BUDGETS_ENABLED", "true").lower() == "true"
    )
    provider_sql_budget_seconds: float = field(
        default_factory=lambda: _provider_seconds("PROVIDER_SQL_BUDGET_SECONDS", "30")
    )
    provider_synthesis_budget_seconds: float = field(
        default_factory=lambda: _provider_seconds("PROVIDER_SYNTHESIS_BUDGET_SECONDS", "20")
    )



settings = Settings()
