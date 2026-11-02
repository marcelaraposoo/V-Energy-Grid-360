import pytest

from app.core.config import Settings
from app.agent.state.dependencies import get_state_dependencies
from app.agent.state.redis_cache import RedisCacheStore


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
    assert deps.memory_store is None
    assert deps.audit_store is None


@pytest.mark.parametrize("field,value", [
    ("cache_ttl_seconds", 0), ("cache_ttl_seconds", -1),
    ("cache_timeout_seconds", 0), ("cache_timeout_seconds", float("nan")),
    ("cache_timeout_seconds", float("inf")),
])
def test_invalid_enabled_cache_settings_fail_at_startup(field, value):
    with pytest.raises(ValueError):
        Settings(redis_url="redis://redis", gold_data_version="v1", **{field: value})
