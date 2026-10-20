import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "V-Energy Grid 360 API"
    data_source: str = field(default_factory=lambda: os.getenv("DATA_SOURCE", "mock"))
    sqlite_path: str = field(default_factory=lambda: os.getenv("SQLITE_PATH", "data/gold.db"))
    cors_origins: tuple = field(
        default_factory=lambda: tuple(os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","))
    )


settings = Settings()
