"""Supported output language helpers."""

SUPPORTED_TARGET_LANGUAGES = {
    "vi": "Vietnamese",
    "en": "English",
}


def normalize_target_language(language: str | None) -> str:
    """Return a supported target language code, defaulting to Vietnamese."""
    if language is not None and not isinstance(language, str):
        return "vi"
    code = (language or "vi").strip().lower()
    if code not in SUPPORTED_TARGET_LANGUAGES:
        supported = ", ".join(sorted(SUPPORTED_TARGET_LANGUAGES))
        raise ValueError(f"Unsupported target language: {language!r}. Supported: {supported}")
    return code


def target_language_name(language: str | None) -> str:
    """Return the display name for a supported target language code."""
    return SUPPORTED_TARGET_LANGUAGES[normalize_target_language(language)]
