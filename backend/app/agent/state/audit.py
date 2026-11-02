from typing import Protocol

from app.agent.schemas import AuditRecord


class AuditStore(Protocol):
    async def save(self, record: AuditRecord) -> None:
        ...