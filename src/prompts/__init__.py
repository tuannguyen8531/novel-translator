"""Prompt template engine.

Templates live in src/prompts/ as .md files with {{var}} placeholders.
Target-language prompts can live in src/prompts/{target}/.
Usage:
    from src.prompts import render_prompt
    prompt = render_prompt("translator_system", target_language="vi", lang_name="Chinese")
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _resolve_template_path(template_name: str, target_language: str | None = None) -> Path:
    """Resolve a template path, checking target-specific folders first."""
    candidates = []
    if target_language:
        candidates.append(_PROMPTS_DIR / target_language / f"{template_name}.md")
    candidates.append(_PROMPTS_DIR / f"{template_name}.md")

    for path in candidates:
        if path.exists():
            return path

    checked = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Prompt template not found: {checked}")


def render_prompt(template_name: str, target_language: str | None = None, **variables: str) -> str:
    """Load a prompt template and replace {{var}} placeholders.

    Args:
        template_name: Filename without extension (e.g. "translator_system")
        target_language: Optional target language folder (e.g. "vi", "en")
        **variables: Key-value pairs to substitute in the template

    Returns:
        Rendered prompt string

    Raises:
        FileNotFoundError: Template file does not exist
    """
    template_path = _resolve_template_path(template_name, target_language)
    content = template_path.read_text(encoding="utf-8")

    for key, value in variables.items():
        content = content.replace("{{" + key + "}}", value)

    return content.strip()
