"""Prompt template engine.

Templates live in src/prompts/ as .md files with {{var}} placeholders.
Usage:
    from src.prompts import render_prompt
    prompt = render_prompt("translator_system", lang_name="Chinese")
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def render_prompt(template_name: str, **variables: str) -> str:
    """Load a prompt template and replace {{var}} placeholders.

    Args:
        template_name: Filename without extension (e.g. "translator_system")
        **variables: Key-value pairs to substitute in the template

    Returns:
        Rendered prompt string

    Raises:
        FileNotFoundError: Template file does not exist
    """
    template_path = _PROMPTS_DIR / f"{template_name}.md"
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8")

    for key, value in variables.items():
        content = content.replace("{{" + key + "}}", value)

    return content
