"""Invariantes cruzados do contrato de geração; sem provider."""

import pytest
from pydantic import ValidationError

from app.agent.schemas import SQLGenerationResult, SQLGenerationStatus


@pytest.mark.parametrize("sql", [None, "", " \r\n\t"])
def test_ready_requires_nonempty_sql(sql):
    with pytest.raises(ValidationError):
        SQLGenerationResult(status="ready", sql=sql)


@pytest.mark.parametrize("reason", ["", " ", "Motivo incompatível"])
def test_ready_rejects_any_reason(reason):
    with pytest.raises(ValidationError):
        SQLGenerationResult(status="ready", sql="SELECT COUNT(*) FROM dim_uc", reason=reason)


def test_ready_accepts_sql_without_reason():
    result = SQLGenerationResult(status="ready", sql="SELECT COUNT(*) FROM dim_uc")
    assert result.reason is None


NON_READY = [status for status in SQLGenerationStatus if status not in {SQLGenerationStatus.READY, SQLGenerationStatus.KNOWLEDGE}]


@pytest.mark.parametrize("status", NON_READY)
@pytest.mark.parametrize("sql", ["", " ", "SELECT 1"])
def test_non_ready_rejects_any_sql(status, sql):
    with pytest.raises(ValidationError):
        SQLGenerationResult(status=status, sql=sql, reason="Motivo")


@pytest.mark.parametrize("status", NON_READY)
@pytest.mark.parametrize("reason", [None, "", " \t"])
def test_non_ready_requires_nonempty_reason(status, reason):
    with pytest.raises(ValidationError):
        SQLGenerationResult(status=status, reason=reason)


@pytest.mark.parametrize("status", NON_READY)
def test_non_ready_accepts_reason_without_sql(status):
    result = SQLGenerationResult(status=status, reason="Qual município? Ou impedimento identificado.")
    assert result.sql is None
