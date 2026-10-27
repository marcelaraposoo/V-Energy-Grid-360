import pytest

from app.agent import sql_generation_orchestrator
from app.agent.schemas import (
    ProviderErrorType,
    SQLGenerationResult,
    SQLGenerationStatus,
    SQLGuardrailDecision,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


DATABASE_CONTEXT = """
Tabela: consumo_energia
Colunas:
- municipio
- consumo_kwh
""".strip()


@pytest.mark.anyio
async def test_passes_on_first_generation(
    monkeypatch,
):
    calls = 0

    async def fake_generate_sql(**kwargs):
        nonlocal calls
        calls += 1

        return (
            SQLGenerationResult(
                status=SQLGenerationStatus.READY,
                sql=(
                    "SELECT * "
                    "FROM consumo_energia"
                ),
                reason=None,
            ),
            [],
            None,
        )

    monkeypatch.setattr(
        sql_generation_orchestrator,
        "generate_sql",
        fake_generate_sql,
    )

    result = await (
        sql_generation_orchestrator
        .generate_and_validate_sql(
            question="Qual foi o consumo?",
            database_context=DATABASE_CONTEXT,
        )
    )

    assert calls == 1
    assert result.regenerations == 0
    assert result.provider_error is None
    assert result.guardrail is not None

    assert (
        result.guardrail.decision
        == SQLGuardrailDecision.ALLOW
    )


@pytest.mark.anyio
async def test_retries_once_and_then_passes(
    monkeypatch,
):
    calls = []

    async def fake_generate_sql(**kwargs):
        calls.append(kwargs)

        if len(calls) == 1:
            return (
                SQLGenerationResult(
                    status=SQLGenerationStatus.READY,
                    sql="DELETE FROM consumo_energia",
                    reason=None,
                ),
                [],
                None,
            )

        return (
            SQLGenerationResult(
                status=SQLGenerationStatus.READY,
                sql=(
                    "SELECT * "
                    "FROM consumo_energia"
                ),
                reason=None,
            ),
            [],
            None,
        )

    monkeypatch.setattr(
        sql_generation_orchestrator,
        "generate_sql",
        fake_generate_sql,
    )

    result = await (
        sql_generation_orchestrator
        .generate_and_validate_sql(
            question="Qual foi o consumo?",
            database_context=DATABASE_CONTEXT,
        )
    )

    assert len(calls) == 2
    assert result.regenerations == 1
    assert result.provider_error is None

    assert (
        result.guardrail.decision
        == SQLGuardrailDecision.ALLOW
    )

    assert (
        calls[0]["guardrail_feedback"]
        is None
    )

    assert (
        calls[1]["guardrail_feedback"]
        is not None
    )

    assert (
        "DELETE FROM consumo_energia"
        in calls[1]["guardrail_feedback"]
    )


@pytest.mark.anyio
async def test_blocks_after_single_regeneration(
    monkeypatch,
):
    calls = 0

    async def fake_generate_sql(**kwargs):
        nonlocal calls
        calls += 1

        return (
            SQLGenerationResult(
                status=SQLGenerationStatus.READY,
                sql="DELETE FROM consumo_energia",
                reason=None,
            ),
            [],
            None,
        )

    monkeypatch.setattr(
        sql_generation_orchestrator,
        "generate_sql",
        fake_generate_sql,
    )

    result = await (
        sql_generation_orchestrator
        .generate_and_validate_sql(
            question="Qual foi o consumo?",
            database_context=DATABASE_CONTEXT,
        )
    )

    assert calls == 2
    assert result.regenerations == 1

    assert (
        result.guardrail.decision
        == SQLGuardrailDecision.BLOCK
    )


@pytest.mark.anyio
async def test_does_not_retry_non_ready_generation(
    monkeypatch,
):
    calls = 0

    async def fake_generate_sql(**kwargs):
        nonlocal calls
        calls += 1

        return (
            SQLGenerationResult(
                status=(
                    SQLGenerationStatus
                    .OUT_OF_SCOPE
                ),
                sql=None,
                reason="Pergunta fora do domínio.",
            ),
            [],
            None,
        )

    monkeypatch.setattr(
        sql_generation_orchestrator,
        "generate_sql",
        fake_generate_sql,
    )

    result = await (
        sql_generation_orchestrator
        .generate_and_validate_sql(
            question="Quem ganhou a Copa?",
            database_context=DATABASE_CONTEXT,
        )
    )

    assert calls == 1
    assert result.regenerations == 0
    assert result.guardrail is None

    assert (
        result.generation.status
        == SQLGenerationStatus.OUT_OF_SCOPE
    )


@pytest.mark.anyio
async def test_provider_error_stops_flow(
    monkeypatch,
):
    calls = 0

    async def fake_generate_sql(**kwargs):
        nonlocal calls
        calls += 1

        return (
            None,
            [],
            ProviderErrorType.PROVIDER_UNAVAILABLE,
        )

    monkeypatch.setattr(
        sql_generation_orchestrator,
        "generate_sql",
        fake_generate_sql,
    )

    result = await (
        sql_generation_orchestrator
        .generate_and_validate_sql(
            question="Qual foi o consumo?",
            database_context=DATABASE_CONTEXT,
        )
    )

    assert calls == 1
    assert result.regenerations == 0

    assert (
        result.provider_error
        == ProviderErrorType.PROVIDER_UNAVAILABLE
    )