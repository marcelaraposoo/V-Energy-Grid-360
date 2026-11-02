import pytest

from app.agent.state.dependencies import AgentStateDependencies


class FakeAuditStore:
    async def save(self, record):
        pass


class FakeMemoryStore:
    async def get_context(self, session_id):
        return []

    async def append(self, session_id, entry):
        pass


class FakeCacheStore:
    async def get(self, key):
        return None

    async def set(self, key, value, ttl_seconds):
        pass


def test_only_audit_is_required():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
    )

    assert dependencies.audit_store is not None
    assert dependencies.memory_store is None
    assert dependencies.cache_store is None


def test_memory_can_be_configured_without_cache():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        memory_store=FakeMemoryStore(),
    )

    assert dependencies.memory_store is not None
    assert dependencies.cache_store is None


@pytest.mark.parametrize("ttl", [None, 0, -1, True, 1.5])
def test_cache_requires_positive_ttl(ttl):
    with pytest.raises(ValueError):
        AgentStateDependencies(
            audit_store=FakeAuditStore(),
            cache_store=FakeCacheStore(),
            data_version="gold-v1",
            cache_ttl_seconds=ttl,
        )


def test_cache_accepts_positive_ttl():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        cache_store=FakeCacheStore(),
        data_version="gold-v1",
        cache_ttl_seconds=300,
    )

    assert dependencies.cache_store is not None
    assert dependencies.cache_ttl_seconds == 300


def test_default_ttl_and_timeout_with_explicit_snapshot():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(), cache_store=FakeCacheStore(), data_version="gold-v1"
    )

    assert dependencies.cache_ttl_seconds == 300
    assert dependencies.cache_timeout_seconds == 1.0


@pytest.mark.parametrize("version", [None, "", "   "])
def test_enabled_cache_requires_snapshot_version(version):
    with pytest.raises(ValueError, match="data_version"):
        AgentStateDependencies(
            audit_store=FakeAuditStore(), cache_store=FakeCacheStore(), data_version=version
        )


@pytest.mark.parametrize("timeout", [None, 0, -1, float("inf"), float("nan"), True])
def test_enabled_cache_requires_finite_positive_timeout(timeout):
    with pytest.raises(ValueError, match="cache_timeout_seconds"):
        AgentStateDependencies(
            audit_store=FakeAuditStore(), cache_store=FakeCacheStore(),
            data_version="gold-v1", cache_timeout_seconds=timeout,
        )


def test_cache_ttl_remains_configurable():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(), cache_store=FakeCacheStore(), data_version="gold-v1",
        cache_ttl_seconds=60, cache_timeout_seconds=0.5,
    )

    assert dependencies.cache_ttl_seconds == 60
    assert dependencies.cache_timeout_seconds == 0.5
