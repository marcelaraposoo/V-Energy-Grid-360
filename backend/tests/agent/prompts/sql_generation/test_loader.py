import pytest

from app.agent.prompts.sql_generation import loader


@pytest.fixture
def isolated_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        loader,
        "PROMPTS_DIR",
        tmp_path,
    )

    return tmp_path


def create_prompt_files(
    directory,
    contents: dict[str, str] | None = None,
):
    contents = contents or {}

    for filename in loader.PROMPT_FILES:
        content = contents.get(
            filename,
            f"conteúdo de {filename}",
        )

        (directory / filename).write_text(
            content,
            encoding="utf-8",
        )


def test_loads_all_prompt_files(
    isolated_prompts,
):
    create_prompt_files(
        isolated_prompts
    )

    result = (
        loader.load_sql_generation_prompts()
    )

    for filename in loader.PROMPT_FILES:
        expected = (
            f"conteúdo de {filename}"
        )

        assert expected in result


def test_preserves_prompt_order(
    isolated_prompts,
):
    contents = {
        "system.md": "SYSTEM",
        "domain.md": "DOMAIN",
        "security.md": "SECURITY",
        "sql_rules.md": "SQL_RULES",
        "output_contract.md": "OUTPUT_CONTRACT",
    }

    create_prompt_files(
        isolated_prompts,
        contents,
    )

    result = (
        loader.load_sql_generation_prompts()
    )

    assert result == (
        "SYSTEM\n\n"
        "DOMAIN\n\n"
        "SECURITY\n\n"
        "SQL_RULES\n\n"
        "OUTPUT_CONTRACT"
    )


def test_raises_error_when_prompt_file_is_missing(
    isolated_prompts,
):
    create_prompt_files(
        isolated_prompts
    )

    missing_file = (
        isolated_prompts
        / "security.md"
    )

    missing_file.unlink()

    with pytest.raises(
        FileNotFoundError
    ):
        loader.load_sql_generation_prompts()


def test_raises_error_when_prompt_file_is_empty(
    isolated_prompts,
):
    contents = {
        "security.md": "",
    }

    create_prompt_files(
        isolated_prompts,
        contents,
    )

    with pytest.raises(
        ValueError
    ):
        loader.load_sql_generation_prompts()


def test_raises_error_when_prompt_contains_only_whitespace(
    isolated_prompts,
):
    contents = {
        "sql_rules.md": "   \n\t   ",
    }

    create_prompt_files(
        isolated_prompts,
        contents,
    )

    with pytest.raises(
        ValueError
    ):
        loader.load_sql_generation_prompts()


def test_strips_whitespace_from_prompt_files(
    isolated_prompts,
):
    contents = {
        "system.md": "   SYSTEM   ",
        "domain.md": "\nDOMAIN\n",
        "security.md": "\tSECURITY\t",
        "sql_rules.md": " SQL_RULES ",
        "output_contract.md": (
            "\nOUTPUT_CONTRACT\n"
        ),
    }

    create_prompt_files(
        isolated_prompts,
        contents,
    )

    result = (
        loader.load_sql_generation_prompts()
    )

    assert result == (
        "SYSTEM\n\n"
        "DOMAIN\n\n"
        "SECURITY\n\n"
        "SQL_RULES\n\n"
        "OUTPUT_CONTRACT"
    )