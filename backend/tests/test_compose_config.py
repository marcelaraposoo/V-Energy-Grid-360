"""Valida o ambiente renderizado pelo Compose com credenciais apenas sintéticas."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
VARIABLES = (
    "GEMINI_API_KEY", "OPENROUTER_API_KEY", "LOGFIRE_ENABLED", "LOGFIRE_TOKEN",
    "LOGFIRE_SERVICE_NAME", "LOGFIRE_BASE_URL", "GOLD_DATA_VERSION", "BACKEND_ENV_FILE",
)


@pytest.mark.parametrize("configured", [True, False])
def test_compose_forwards_provider_and_observability_configuration(tmp_path, configured):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker CLI não instalado; renderização não exige engine.")
    version = subprocess.run([docker, "compose", "version"], capture_output=True, timeout=20)
    if version.returncode:
        pytest.skip("Plugin Docker Compose indisponível.")
    values = {"GOLD_DATA_VERSION": "synthetic-v1"}
    if configured:
        values.update(
            GEMINI_API_KEY="synthetic-gemini", OPENROUTER_API_KEY="synthetic-openrouter",
            LOGFIRE_ENABLED="true", LOGFIRE_TOKEN="synthetic-logfire",
            LOGFIRE_SERVICE_NAME="synthetic-backend", LOGFIRE_BASE_URL="https://example.invalid",
        )
    env_file = tmp_path / "synthetic.env"
    env_file.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if key not in VARIABLES}
    environment["BACKEND_ENV_FILE"] = str(env_file)
    result = subprocess.run(
        [docker, "compose", "--env-file", str(env_file), "-f", str(ROOT / "compose.yaml"),
         "config", "--format", "json"],
        env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, "Falha ao renderizar a configuração sintética do Compose."
    backend = json.loads(result.stdout)["services"]["backend"]
    effective = backend["environment"]
    assert effective["GOLD_DATA_VERSION"] == "synthetic-v1"
    assert effective["DATA_SOURCE"] == "sqlite"
    assert effective["SQLITE_PATH"] == "/data/gold/gold.db"
    assert effective["PORTAL_DB_PATH"] == "/data/portal/portal.db"
    assert effective["REDIS_URL"] == "redis://redis:6379/0"
    for key in ("GEMINI_API_KEY", "OPENROUTER_API_KEY", "LOGFIRE_TOKEN", "LOGFIRE_BASE_URL"):
        assert effective.get(key, "") == values.get(key, "")
    assert effective.get("LOGFIRE_ENABLED", "false") == ("true" if configured else "false")
    assert effective.get("LOGFIRE_SERVICE_NAME", "v-energy-grid-360-backend") == values.get(
        "LOGFIRE_SERVICE_NAME", "v-energy-grid-360-backend",
    )
    assert not backend.get("env_file")
    assert all(mount.get("target") != "/app/.env" for mount in backend.get("volumes", []))
