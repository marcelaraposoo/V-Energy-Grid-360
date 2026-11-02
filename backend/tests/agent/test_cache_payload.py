import pytest

from app.agent.schemas import PostProcessingResult
from app.agent.state.cache import deserialize_cache_value, serialize_cache_value


def test_payload_round_trips_as_json_and_is_revalidated():
    value = PostProcessingResult(answer="Receita por município.", assumptions=["Período fixo."])

    payload = serialize_cache_value(value)
    restored = deserialize_cache_value(payload.encode("utf-8"))

    assert isinstance(payload, str)
    assert restored == value
    assert restored is not value


@pytest.mark.parametrize("payload", [
    "não é JSON", "null", "[]", "{}", '{"answer":""}', '{"answer":42}',
    '{"answer":"ok", "assumptions":"contrato antigo"}',
    '{"answer":"ok", "visualization":{"type":"desconhecido"}}',
])
def test_invalid_or_incompatible_json_is_a_miss(payload):
    assert deserialize_cache_value(payload) is None


def test_serialization_rejects_models_created_without_validation():
    with pytest.raises(ValueError):
        serialize_cache_value(PostProcessingResult.model_construct(answer=""))
