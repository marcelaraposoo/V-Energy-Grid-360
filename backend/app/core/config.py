import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Carrega backend/.env (se existir). Variáveis já definidas no ambiente têm prioridade.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

CORS_PADRAO = "http://localhost:5173,http://127.0.0.1:5173"


@dataclass(frozen=True)
class Settings:
    app_name: str = "V-Energy Grid 360 API"
    data_source: str = field(default_factory=lambda: os.getenv("DATA_SOURCE", "mock"))
    sqlite_path: str = field(default_factory=lambda: os.getenv("SQLITE_PATH", "data/gold.db"))
    cors_origins: tuple = field(
        default_factory=lambda: tuple(o.strip() for o in os.getenv("CORS_ORIGINS", CORS_PADRAO).split(",") if o.strip())
    )


settings = Settings()
