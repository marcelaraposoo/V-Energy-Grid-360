from app.agent.schemas import AgentOutcome, AuditRecord
from app.agent.state.audit import AuditStore


class FakeAuditStore:
    def __init__(self):
        self.records: list[AuditRecord] = []

    async def save(self, record: AuditRecord) -> None:
        self.records.append(record)


def accepts_audit_store(store: AuditStore) -> AuditStore:
    return store


def test_fake_audit_store_matches_contract():
    store = FakeAuditStore()

    assert accepts_audit_store(store) is store