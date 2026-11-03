"""Auditoria interna no portal.db, com I/O fora do event loop."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import timezone
from pathlib import Path

from app.agent.schemas import AuditRecord


_DDL = """
CREATE TABLE IF NOT EXISTS agent_audit (
    request_id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT,
    timestamp TEXT NOT NULL,
    question TEXT NOT NULL,
    outcome TEXT NOT NULL,
    cache_hit INTEGER NOT NULL CHECK (cache_hit IN (0, 1)),
    sql TEXT,
    row_count INTEGER,
    truncated INTEGER CHECK (truncated IN (0, 1)),
    provider_error TEXT,
    regenerations INTEGER NOT NULL,
    final_answer TEXT
)
"""


class SQLiteAuditStore:
    def __init__(self, path: str) -> None:
        # Construção não abre banco nem cria diretório.
        self.path = path

    async def save(self, record: AuditRecord) -> None:
        validated = AuditRecord.model_validate(record.model_dump(), strict=True)
        await asyncio.to_thread(self._save, validated)

    def _save(self, record: AuditRecord) -> None:
        # Mesma separação de diretório/transação do SqliteOrdensStore.
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        timestamp = record.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        timestamp = timestamp.astimezone(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.path, timeout=1.0)) as connection:
            connection.execute("PRAGMA busy_timeout=1000")
            with connection:
                connection.execute(_DDL)
                connection.execute(
                    "INSERT INTO agent_audit (request_id,session_id,timestamp,question,"
                    "outcome,cache_hit,sql,row_count,truncated,provider_error,regenerations,"
                    "final_answer) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(request_id) DO NOTHING",
                    (
                        record.request_id, record.session_id, timestamp, record.question,
                        record.outcome.value, int(record.cache_hit), record.sql, record.row_count,
                        None if record.truncated is None else int(record.truncated),
                        record.provider_error.value if record.provider_error else None,
                        record.regenerations, record.final_answer,
                    ),
                )
