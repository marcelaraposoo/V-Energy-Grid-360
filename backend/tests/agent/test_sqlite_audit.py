import asyncio
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.agent.schemas import AgentOutcome, AuditRecord, ProviderErrorType
from app.agent.state.sqlite_audit import SQLiteAuditStore
from app.repositories.ordens_store import SqliteOrdensStore


def test_audit_is_lazy_and_persists_exact_record_fields_in_portal(tmp_path):
    path = tmp_path / "portal" / "portal.db"
    store = SQLiteAuditStore(str(path))
    assert not path.parent.exists()
    record = AuditRecord(
        request_id="r1", session_id="s1", question="Qual a receita?",
        timestamp=datetime(2026, 6, 1, 12, tzinfo=timezone(timedelta(hours=-3))),
        outcome=AgentOutcome.PROVIDER_ERROR, cache_hit=False, sql="SELECT receita_total FROM kpis_mensal",
        row_count=3, truncated=True, provider_error=ProviderErrorType.TIMEOUT,
        regenerations=1, final_answer="Tente novamente.",
    )
    asyncio.run(store.save(record))
    asyncio.run(store.save(record))
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM agent_audit").fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert set(row) == set(AuditRecord.model_fields)
    assert row["timestamp"] == "2026-06-01T15:00:00+00:00"
    assert row["outcome"] == "provider_error"
    assert row["cache_hit"] == 0 and row["truncated"] == 1
    assert row["provider_error"] == "timeout"
    assert row["sql"] == record.sql
    assert row["request_id"] == "r1" and row["regenerations"] == 1


def test_audit_coexists_with_portal_orders_and_handles_null_metadata(tmp_path):
    path = str(tmp_path / "portal.db")
    orders = SqliteOrdensStore(path)
    order = orders.criar({"uc_id": "UC-TESTE"})
    orders.close()
    asyncio.run(SQLiteAuditStore(path).save(AuditRecord(
        request_id="hit", question="Consumo?", outcome=AgentOutcome.ANSWERED, cache_hit=True,
    )))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ordens_inspecao WHERE id=?", (order["id"],)).fetchone() == (1,)
        assert conn.execute("SELECT cache_hit,truncated,sql FROM agent_audit").fetchone() == (1, None, None)


def test_sqlite_io_runs_in_a_worker_thread(monkeypatch):
    store = SQLiteAuditStore(":memory:")
    thread_ids = []
    def save(_record):
        thread_ids.append(threading.get_ident())
        time.sleep(0.03)
    monkeypatch.setattr(store, "_save", save)
    asyncio.run(store.save(AuditRecord(request_id="r", question="Q", outcome=AgentOutcome.NO_DATA)))
    assert thread_ids and thread_ids[0] != threading.get_ident()


def test_concurrent_requests_have_unique_audit_records(tmp_path):
    path = str(tmp_path / "portal.db")
    async def run():
        await asyncio.gather(*(SQLiteAuditStore(path).save(AuditRecord(
            request_id=f"r{i}", question="Q", outcome=AgentOutcome.ANSWERED,
        )) for i in range(12)))
    asyncio.run(run())
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_audit").fetchone() == (12,)


def test_busy_portal_times_out_instead_of_waiting_indefinitely(tmp_path):
    path = str(tmp_path / "portal.db")
    with sqlite3.connect(path) as lock:
        lock.execute("BEGIN EXCLUSIVE")
        with pytest.raises(sqlite3.OperationalError):
            asyncio.run(SQLiteAuditStore(path).save(AuditRecord(
                request_id="busy", question="Q", outcome=AgentOutcome.ANSWERED,
            )))
