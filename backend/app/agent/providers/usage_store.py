import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Callable

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
LOCK_TIMEOUT_SECONDS = 0.1
RECORD_TIMEOUT_SECONDS = 0.25
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="usage-store")
_slot = BoundedSemaphore(1)
logger = logging.getLogger(__name__)


async def record_attempt_best_effort(register: Callable[[], None]) -> None:
    """I/O fora do loop, espera limitada e no máximo um trabalho pendente.

    Timeout não interrompe I/O do SO em andamento. Enquanto o worker estiver
    ocupado, novos registros são descartados em vez de acumular threads/fila.
    """
    if not _slot.acquire(blocking=False):
        return

    def record() -> None:
        try:
            register()
        except Exception as error:
            logger.warning("Telemetria local indisponível provider=openrouter exception_type=%s",
                           type(error).__name__)
        finally:
            _slot.release()

    try:
        future = _executor.submit(record)
    except Exception as error:
        _slot.release()
        logger.warning("Telemetria local não agendada exception_type=%s", type(error).__name__)
        return
    try:
        await asyncio.wait_for(
            asyncio.shield(asyncio.wrap_future(future)), timeout=RECORD_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("Telemetria local excedeu timeout provider=openrouter")


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
        str(USAGE_LOCK_PATH), timeout=LOCK_TIMEOUT_SECONDS,
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
        str(USAGE_LOCK_PATH), timeout=LOCK_TIMEOUT_SECONDS,
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
