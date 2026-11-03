import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.core.config import Settings
from app.agent.state.dependencies import get_state_dependencies
from app.agent.state.redis_cache import RedisCacheStore
from app.agent.state.redis_memory import RedisMemoryStore
from app.agent.state.sqlite_audit import SQLiteAuditStore


def test_cache_is_disabled_without_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("GOLD_DATA_VERSION", raising=False)
    monkeypatch.delenv("CACHE_TTL_SECONDS", raising=False)
    monkeypatch.delenv("CACHE_TIMEOUT_SECONDS", raising=False)
    config = Settings()
    monkeypatch.setattr("app.core.config.settings", config)
    assert config.cache_ttl_seconds == 300
    assert config.cache_timeout_seconds == 1
    assert get_state_dependencies().cache_store is None


@pytest.mark.parametrize("version", [None, "", "   "])
def test_enabled_cache_requires_explicit_gold_version(version):
    with pytest.raises(ValueError, match="GOLD_DATA_VERSION"):
        Settings(redis_url="redis://redis", gold_data_version=version)


def test_environment_configures_one_runtime_cache(monkeypatch):
    for key, value in {
        "REDIS_URL": "redis://redis:6379/0", "GOLD_DATA_VERSION": "snapshot-v2",
        "CACHE_TTL_SECONDS": "60", "CACHE_TIMEOUT_SECONDS": "0.5",
    }.items():
        monkeypatch.setenv(key, value)
    config = Settings()
    monkeypatch.setattr("app.core.config.settings", config)
    deps = get_state_dependencies()
    assert isinstance(deps.cache_store, RedisCacheStore)
    assert deps.data_version == "snapshot-v2"
    assert deps.cache_ttl_seconds == 60
    assert deps.cache_timeout_seconds == 0.5
    assert isinstance(deps.memory_store, RedisMemoryStore)
    assert isinstance(deps.audit_store, SQLiteAuditStore)
    assert deps.audit_store.path == config.portal_db_path
    assert config.memory_ttl_seconds == 86400
    assert config.memory_timeout_seconds == 1


@pytest.mark.parametrize("field,value", [
    ("cache_ttl_seconds", 0), ("cache_ttl_seconds", -1),
    ("cache_timeout_seconds", 0), ("cache_timeout_seconds", float("nan")),
    ("cache_timeout_seconds", float("inf")),
])
def test_invalid_enabled_cache_settings_fail_at_startup(field, value):
    with pytest.raises(ValueError):
        Settings(redis_url="redis://redis", gold_data_version="v1", **{field: value})


def test_memory_environment_configuration(monkeypatch):
    monkeypatch.setenv("MEMORY_TTL_SECONDS", "120")
    monkeypatch.setenv("MEMORY_TIMEOUT_SECONDS", "0.25")
    config = Settings(redis_url="redis://redis", gold_data_version="v1")
    monkeypatch.setattr("app.core.config.settings", config)
    assert config.memory_ttl_seconds == 120
    assert get_state_dependencies().memory_timeout_seconds == 0.25


@pytest.mark.parametrize("field,value", [
    ("memory_ttl_seconds", 0), ("memory_ttl_seconds", -1),
    ("memory_timeout_seconds", 0), ("memory_timeout_seconds", float("nan")),
    ("memory_timeout_seconds", float("inf")),
])
def test_invalid_memory_configuration_is_rejected(field, value):
    with pytest.raises(ValueError):
        Settings(redis_url="redis://redis", gold_data_version="v1", **{field: value})


@pytest.mark.parametrize("field,value,message", [
    ("GOLD_DATA_VERSION", " ", "GOLD_DATA_VERSION"),
    ("CACHE_TTL_SECONDS", "0", "cache_ttl_seconds"),
    ("MEMORY_TIMEOUT_SECONDS", "nan", "cache_timeout_seconds"),
])
def test_backend_import_still_fails_fast_for_invalid_startup_config(field, value, message):
    env = {
        **os.environ,
        "REDIS_URL": "redis://redis", "GOLD_DATA_VERSION": "startup-test-v1",
        "CACHE_TTL_SECONDS": "300", "CACHE_TIMEOUT_SECONDS": "1",
        "MEMORY_TTL_SECONDS": "86400", "MEMORY_TIMEOUT_SECONDS": "1",
        field: value,
    }
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=Path(__file__).resolve().parents[2], env=env,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "ValueError" in result.stderr and message in result.stderr
