import pytest

from app.agent.provider_responses import (
    DEFAULT_PROVIDER_MESSAGE,
    PROVIDER_MESSAGES,
    get_provider_message,
)
from app.agent.schemas import ProviderErrorType


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            ProviderErrorType.RATE_LIMITED,
            PROVIDER_MESSAGES[
                ProviderErrorType.RATE_LIMITED
            ],
        ),
        (
            ProviderErrorType.QUOTA_EXHAUSTED,
            PROVIDER_MESSAGES[
                ProviderErrorType.QUOTA_EXHAUSTED
            ],
        ),
        (
            ProviderErrorType.PROVIDER_UNAVAILABLE,
            PROVIDER_MESSAGES[
                ProviderErrorType.PROVIDER_UNAVAILABLE
            ],
        ),
        (
            ProviderErrorType.TIMEOUT,
            PROVIDER_MESSAGES[
                ProviderErrorType.TIMEOUT
            ],
        ),
        (
            ProviderErrorType.CONNECTION_ERROR,
            PROVIDER_MESSAGES[
                ProviderErrorType.CONNECTION_ERROR
            ],
        ),
        (
            ProviderErrorType.INVALID_OUTPUT,
            PROVIDER_MESSAGES[
                ProviderErrorType.INVALID_OUTPUT
            ],
        ),
        (
            ProviderErrorType.BAD_REQUEST,
            PROVIDER_MESSAGES[
                ProviderErrorType.BAD_REQUEST
            ],
        ),
        (
            ProviderErrorType.UNAUTHORIZED,
            PROVIDER_MESSAGES[
                ProviderErrorType.UNAUTHORIZED
            ],
        ),
        (
            ProviderErrorType.FORBIDDEN,
            PROVIDER_MESSAGES[
                ProviderErrorType.FORBIDDEN
            ],
        ),
        (
            ProviderErrorType.CONFIGURATION_ERROR,
            PROVIDER_MESSAGES[
                ProviderErrorType.CONFIGURATION_ERROR
            ],
        ),
        (
            ProviderErrorType.UNKNOWN,
            PROVIDER_MESSAGES[
                ProviderErrorType.UNKNOWN
            ],
        ),
    ],
)
def test_returns_message_for_provider_error(
    error,
    expected,
):
    assert (
        get_provider_message(error)
        == expected
    )


def test_none_returns_default_message():
    assert (
        get_provider_message(None)
        == DEFAULT_PROVIDER_MESSAGE
    )


def test_all_provider_errors_have_message():
    for error in ProviderErrorType:
        assert error in PROVIDER_MESSAGES


def test_all_messages_are_non_empty():
    for message in PROVIDER_MESSAGES.values():
        assert isinstance(message, str)
        assert message.strip()


def test_messages_do_not_expose_provider_names():
    forbidden_terms = (
        "gemini",
        "openrouter",
        "nemotron",
        "gemma",
        "google",
        "nvidia",
    )

    for message in PROVIDER_MESSAGES.values():
        lower_message = message.lower()

        for term in forbidden_terms:
            assert term not in lower_message