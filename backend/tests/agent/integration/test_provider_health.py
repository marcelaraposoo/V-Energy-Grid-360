import os

import pytest
from pydantic import BaseModel
from typing import Literal

from app.agent.providers.gemini import run_gemini
from app.agent.providers.openrouter import run_openrouter


RUN_INTEGRATION = (
    os.getenv("RUN_LLM_INTEGRATION") == "1"
)

pytestmark = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason=(
        "Health check real de providers desativado. "
        "Defina RUN_LLM_INTEGRATION=1 para executar."
    ),
)


class HealthCheckResult(BaseModel):
    status: Literal["ok"]


PROMPT = (
    "Este é um teste técnico de saúde do provider. "
    "Retorne apenas o resultado estruturado solicitado "
    "com status igual a 'ok'."
)

INSTRUCTIONS = (
    "Siga exatamente o schema de saída. "
    "Não adicione explicações."
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def assert_healthy(
    output,
    attempt,
):
    assert attempt.success is True, (
        f"Provider falhou. "
        f"provider={attempt.provider.value}, "
        f"model={attempt.model}, "
        f"error={attempt.error_type}, "
        f"latency_ms={attempt.latency_ms}"
    )

    assert output is not None

    assert isinstance(
        output,
        HealthCheckResult,
    )

    assert output.status == "ok"


@pytest.mark.anyio
async def test_gemini_health():
    output, attempt = await run_gemini(
        PROMPT,
        output_type=HealthCheckResult,
        instructions=INSTRUCTIONS,
    )

    assert_healthy(
        output,
        attempt,
    )


@pytest.mark.anyio
async def test_cohere_health():
    output, attempt = await run_openrouter(
        "cohere/north-mini-code:free",
        PROMPT,
        output_type=HealthCheckResult,
        instructions=INSTRUCTIONS,
    )

    assert_healthy(
        output,
        attempt,
    )


@pytest.mark.anyio
async def test_nemotron_ultra_health():
    output, attempt = await run_openrouter(
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        PROMPT,
        output_type=HealthCheckResult,
        instructions=INSTRUCTIONS,
    )

    assert_healthy(
        output,
        attempt,
    )