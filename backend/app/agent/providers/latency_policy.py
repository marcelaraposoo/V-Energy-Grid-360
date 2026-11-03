"""Estado efêmero da C3, sem conteúdo ou persistência entre requisições."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from time import monotonic

from app.core.config import settings


@dataclass
class RequestPolicy:
    preferred: tuple[str, str] | None = None


request_policy: ContextVar[RequestPolicy | None] = ContextVar("provider_policy", default=None)
phase_deadline: ContextVar[float | None] = ContextVar("provider_deadline", default=None)
attempt_timeout: ContextVar[float | None] = ContextVar("provider_timeout", default=None)


@contextmanager
def request_scope():
    token = request_policy.set(RequestPolicy())
    try:
        yield request_policy.get()
    finally:
        request_policy.reset(token)


def provider_request(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        with request_scope():
            return await function(*args, **kwargs)
    return wrapped


def provider_phase(name):
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            budget = getattr(settings, f"provider_{name}_budget_seconds")
            deadline = monotonic() + budget if settings.provider_phase_budgets_enabled else None
            token = phase_deadline.set(deadline)
            try:
                return await function(*args, **kwargs)
            finally:
                phase_deadline.reset(token)
        return wrapped
    return decorate


def timeout_for_attempt(default):
    override = attempt_timeout.get()
    return default if override is None else override
