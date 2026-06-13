"""Illustration markers shared by translation quality checks and packaging."""

import re
from collections import Counter


ILLUSTRATION_MARKER_RE = re.compile(
    r"\[\[ILLUSTRATION:([A-Za-z0-9][A-Za-z0-9._-]*)\]\]"
)


def parse_illustration_marker(text: str) -> str | None:
    """Return the referenced filename when text is exactly one illustration marker."""
    match = ILLUSTRATION_MARKER_RE.fullmatch(text.strip())
    return match.group(1) if match else None


def illustration_marker_counts(text: str) -> Counter[str]:
    """Count illustration filenames referenced by markers in text."""
    return Counter(ILLUSTRATION_MARKER_RE.findall(text))


def detach_illustration_markers(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Remove marker paragraphs and remember their positions among text paragraphs."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    text_paragraphs: list[str] = []
    placements: list[tuple[int, str]] = []

    for paragraph in paragraphs:
        filename = parse_illustration_marker(paragraph)
        if filename:
            placements.append((len(text_paragraphs), f"[[ILLUSTRATION:{filename}]]"))
        else:
            text_paragraphs.append(paragraph)

    return "\n\n".join(text_paragraphs), placements


def restore_illustration_markers(
    translated_text: str,
    placements: list[tuple[int, str]],
) -> str:
    """Insert detached markers back between translated paragraphs."""
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n", translated_text)
        if part.strip()
    ]
    inserted = 0
    for paragraph_index, marker in placements:
        insertion_index = min(paragraph_index + inserted, len(paragraphs))
        paragraphs.insert(insertion_index, marker)
        inserted += 1
    return "\n\n".join(paragraphs)
