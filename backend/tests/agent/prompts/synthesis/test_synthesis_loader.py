import pytest

from app.agent.prompts.synthesis import loader


def test_loads_all_prompt_files():
    prompt = loader.load_synthesis_prompts()

    assert prompt.strip()
    assert "# Papel" in prompt
    assert "## Segurança" in prompt
    assert "## Contrato de Saída" in prompt


def test_preserves_prompt_order():
    prompt = loader.load_synthesis_prompts()

    assert (
        prompt.index("# Papel")
        < prompt.index("## Segurança")
        < prompt.index("## Contrato de Saída")
    )


def test_raises_error_when_prompt_file_is_missing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(loader, "PROMPTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        loader.load_synthesis_prompts()


def test_raises_error_when_prompt_file_is_empty(
    tmp_path, monkeypatch
):
    for filename in loader.PROMPT_FILES:
        (tmp_path / filename).write_text(
            "conteúdo", encoding="utf-8"
        )

    (tmp_path / "security.md").write_text(
        "   \n", encoding="utf-8"
    )

    monkeypatch.setattr(loader, "PROMPTS_DIR", tmp_path)

    with pytest.raises(ValueError):
        loader.load_synthesis_prompts()

def test_prompt_allows_simple_aggregations_only_when_complete():
    prompt = loader.load_synthesis_prompts()

    assert "Não calcule novos valores" not in prompt
    assert "estiver completo" in prompt
    assert "guardrail_feedback" in prompt
    assert "Números escritos na pergunta" in prompt
    assert "datas que aparecem no SQL executado" in prompt