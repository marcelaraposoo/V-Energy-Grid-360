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


def test_cache_requires_positive_ttl():
    with pytest.raises(ValueError):
        AgentStateDependencies(
            audit_store=FakeAuditStore(),
            cache_store=FakeCacheStore(),
        )


def test_cache_accepts_positive_ttl():
    dependencies = AgentStateDependencies(
        audit_store=FakeAuditStore(),
        cache_store=FakeCacheStore(),
        cache_ttl_seconds=300,
    )

    assert dependencies.cache_store is not None
    assert dependencies.cache_ttl_seconds == 300