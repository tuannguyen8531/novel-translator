"""
Glossary Service — JSON-based per-novel glossary management.

Each novel gets its own glossary file at glossary/{novel_name}.json.
Structure:
{
    "terms": {
        "原始术语": "Bản dịch tiếng Việt",
        "李明": "Lý Minh"
    },
    "chapter_summaries": {
        "1": "Summary of chapter 1...",
        "2": "Summary of chapter 2..."
    }
}
"""

import json
import os
from pathlib import Path

GLOSSARY_DIR = Path("glossary")


def _glossary_path(novel_name: str) -> Path:
    """Get path to glossary file for a novel."""
    return GLOSSARY_DIR / f"{novel_name}.json"


def _ensure_dir():
    """Create glossary directory if it doesn't exist."""
    GLOSSARY_DIR.mkdir(parents=True, exist_ok=True)


def load_glossary(novel_name: str) -> dict[str, str]:
    """Load term glossary for a novel. Returns empty dict if not found."""
    path = _glossary_path(novel_name)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("terms", {})


def save_glossary(novel_name: str, terms: dict[str, str]):
    """Save/merge terms into the novel's glossary."""
    _ensure_dir()
    path = _glossary_path(novel_name)

    # Load existing data
    existing_data = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    # Merge terms (new terms override old ones)
    existing_terms = existing_data.get("terms", {})
    existing_terms.update(terms)
    existing_data["terms"] = existing_terms

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


def load_chapter_summary(novel_name: str, chapter_number: int) -> str:
    """Load summary for a specific chapter. Returns empty string if not found."""
    path = _glossary_path(novel_name)
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    summaries = data.get("chapter_summaries", {})
    return summaries.get(str(chapter_number), "")


def load_chapter_summaries_recent(
    novel_name: str,
    current_chapter: int,
    max_count: int = 3,
) -> str:
    """
    Load the most recent chapter summaries (up to max_count).

    For chapter 10 with max_count=3, loads summaries for chapters 9, 8, 7.
    Returns a formatted string ready for inclusion in prompts.
    """
    path = _glossary_path(novel_name)
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    summaries = data.get("chapter_summaries", {})

    # Collect recent summaries (most recent first)
    parts = []
    for ch in range(current_chapter - 1, max(0, current_chapter - 1 - max_count), -1):
        summary = summaries.get(str(ch), "")
        if summary:
            parts.append(f"Chapter {ch}: {summary}")

    if not parts:
        return ""

    # Reverse so oldest is first (natural reading order)
    parts.reverse()
    return "\n\n".join(parts)


def save_chapter_summary(novel_name: str, chapter_number: int, summary: str):
    """Save a chapter summary."""
    _ensure_dir()
    path = _glossary_path(novel_name)

    existing_data = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    summaries = existing_data.get("chapter_summaries", {})
    summaries[str(chapter_number)] = summary
    existing_data["chapter_summaries"] = summaries

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


def format_glossary_for_prompt(terms: dict[str, str]) -> str:
    """Format glossary as a string for inclusion in LLM prompts."""
    if not terms:
        return ""
    lines = ["=== GLOSSARY (use these translations consistently) ==="]
    for original, translated in terms.items():
        lines.append(f"  {original} → {translated}")
    lines.append("=== END GLOSSARY ===")
    return "\n".join(lines)
