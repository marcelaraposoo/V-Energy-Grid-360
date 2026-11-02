"""Restrições conhecidas de envio de dados; ausência/erro de opção é fail-safe."""

RESTRICTED_MODELS = frozenset({"nvidia/nemotron-3-ultra-550b-a55b:free"})


def allows_model(model_name: str, payload_policy: str) -> bool:
    return model_name not in RESTRICTED_MODELS or payload_policy == "synthetic"
