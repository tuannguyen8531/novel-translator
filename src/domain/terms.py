"""Domain rules for glossary term selection."""

import re


MIN_TERM_FREQUENCY = 3


def count_occurrences(text: str, term: str) -> int:
    """Count case-insensitive occurrences of term."""
    if not term or len(term) < 2:
        return 0
    escaped = re.escape(term)
    return len(re.findall(escaped, text, re.IGNORECASE))


def filter_terms_by_frequency(text: str, terms: dict[str, str], min_count: int) -> dict[str, str]:
    """Keep only terms that appear at least min_count times in the text."""
    filtered = {}
    for original, translation in terms.items():
        count = count_occurrences(text, original)
        if count >= min_count:
            filtered[original] = translation
    return filtered
