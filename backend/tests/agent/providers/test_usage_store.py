import json

from datetime import datetime, timedelta, timezone

import pytest

from app.agent.providers import usage_store


@pytest.fixture
def isolated_usage_store(tmp_path, monkeypatch):
    """
    Redireciona os arquivos de estado e lock para um diretório
    temporário, evitando alterar o .runtime real durante os testes.
    """

    state_path = tmp_path / "openrouter_usage.json"
    lock_path = tmp_path / "openrouter_usage.lock"

    monkeypatch.setattr(
        usage_store,
        "USAGE_STATE_PATH",
        state_path,
    )

    monkeypatch.setattr(
        usage_store,
        "USAGE_LOCK_PATH",
        lock_path,
    )

    return state_path


def test_returns_empty_list_when_state_does_not_exist(
    isolated_usage_store,
):
    timestamps = usage_store.get_request_timestamps()

    assert timestamps == []


def test_creates_state_file_when_it_does_not_exist(
    isolated_usage_store,
):
    usage_store.get_request_timestamps()

    assert isolated_usage_store.exists()

    with isolated_usage_store.open(
        "r",
        encoding="utf-8",
    ) as file:
        state = json.load(file)

    assert state == {"requests": []}


def test_registers_request_attempt(
    isolated_usage_store,
):
    usage_store.register_request_attempt()

    timestamps = usage_store.get_request_timestamps()

    assert len(timestamps) == 1


def test_registered_timestamp_is_valid_utc(
    isolated_usage_store,
):
    usage_store.register_request_attempt()

    timestamps = usage_store.get_request_timestamps()

    request_time = datetime.fromisoformat(
        timestamps[0]
    )

    assert request_time.tzinfo is not None
    assert request_time.utcoffset() == timedelta(0)


def test_registers_multiple_request_attempts(
    isolated_usage_store,
):
    usage_store.register_request_attempt()
    usage_store.register_request_attempt()
    usage_store.register_request_attempt()

    timestamps = usage_store.get_request_timestamps()

    assert len(timestamps) == 3


def test_preserves_recent_requests(
    isolated_usage_store,
):
    recent_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=2)
    ).isoformat()

    state = {
        "requests": [
            recent_timestamp,
        ]
    }

    with isolated_usage_store.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(state, file)

    timestamps = usage_store.get_request_timestamps()

    assert len(timestamps) == 1
    assert timestamps[0] == recent_timestamp


def test_removes_requests_older_than_24_hours(
    isolated_usage_store,
):
    expired_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=25)
    ).isoformat()

    state = {
        "requests": [
            expired_timestamp,
        ]
    }

    with isolated_usage_store.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(state, file)

    timestamps = usage_store.get_request_timestamps()

    assert timestamps == []


def test_keeps_recent_and_removes_expired_requests(
    isolated_usage_store,
):
    recent_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=3)
    ).isoformat()

    expired_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=30)
    ).isoformat()

    state = {
        "requests": [
            expired_timestamp,
            recent_timestamp,
        ]
    }

    with isolated_usage_store.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(state, file)

    timestamps = usage_store.get_request_timestamps()

    assert len(timestamps) == 1
    assert recent_timestamp in timestamps
    assert expired_timestamp not in timestamps


def test_persists_cleanup_to_file(
    isolated_usage_store,
):
    recent_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=1)
    ).isoformat()

    expired_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(days=2)
    ).isoformat()

    state = {
        "requests": [
            expired_timestamp,
            recent_timestamp,
        ]
    }

    with isolated_usage_store.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(state, file)

    usage_store.get_request_timestamps()

    with isolated_usage_store.open(
        "r",
        encoding="utf-8",
    ) as file:
        persisted_state = json.load(file)

    assert persisted_state["requests"] == [
        recent_timestamp
    ]


def test_register_attempt_after_removing_expired_requests(
    isolated_usage_store,
):
    expired_timestamp = (
        datetime.now(timezone.utc)
        - timedelta(hours=26)
    ).isoformat()

    state = {
        "requests": [
            expired_timestamp,
        ]
    }

    with isolated_usage_store.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(state, file)

    usage_store.register_request_attempt()

    timestamps = usage_store.get_request_timestamps()

    assert len(timestamps) == 1
    assert expired_timestamp not in timestamps