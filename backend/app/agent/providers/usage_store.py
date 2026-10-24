import json

from datetime import datetime, timedelta, timezone
from pathlib import Path

from filelock import FileLock


USAGE_STATE_PATH = Path(
    ".runtime/openrouter_usage.json"
)

USAGE_LOCK_PATH = Path(
    ".runtime/openrouter_usage.lock"
)

WINDOW_HOURS = 24


def _ensure_runtime_directory() -> None:
    USAGE_STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def _load_state() -> dict:
    if not USAGE_STATE_PATH.exists():
        return {
            "requests": [],
        }

    with USAGE_STATE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def _save_state(
    state: dict,
) -> None:
    _ensure_runtime_directory()

    with USAGE_STATE_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False,
        )


def _remove_expired_requests(
    timestamps: list[str],
) -> list[str]:

    now = datetime.now(
        timezone.utc
    )

    window_start = (
        now
        - timedelta(
            hours=WINDOW_HOURS
        )
    )

    valid_requests = []

    for timestamp in timestamps:
        request_time = (
            datetime.fromisoformat(
                timestamp
            )
        )

        if request_time >= window_start:
            valid_requests.append(
                timestamp
            )

    return valid_requests


def get_request_timestamps() -> list[str]:
    _ensure_runtime_directory()

    with FileLock(
        str(USAGE_LOCK_PATH)
    ):
        state = _load_state()

        valid_requests = (
            _remove_expired_requests(
                state.get(
                    "requests",
                    [],
                )
            )
        )

        state["requests"] = (
            valid_requests
        )

        _save_state(
            state
        )

        return valid_requests


def register_request_attempt() -> None:
    _ensure_runtime_directory()

    with FileLock(
        str(USAGE_LOCK_PATH)
    ):
        state = _load_state()

        valid_requests = (
            _remove_expired_requests(
                state.get(
                    "requests",
                    [],
                )
            )
        )

        valid_requests.append(
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        state["requests"] = (
            valid_requests
        )

        _save_state(
            state
        )