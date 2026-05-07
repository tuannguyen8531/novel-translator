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
    },
    "source_language": "chinese",
    "translated_chapters": [1, 2, 3]
}
"""

import fcntl
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


def _read_json_locked(path: Path) -> dict:
    """Read JSON file with shared lock."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _write_json_locked(path: Path, data: dict):
    """Write JSON file with exclusive lock."""
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _merge_json_locked(path: Path, updater: callable) -> dict:
    """Atomically read-modify-write JSON with exclusive lock.

    Args:
        path: File path
        updater: Function that takes existing data dict and returns updated dict
    """
    _ensure_dir()
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            try:
                existing_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                existing_data = {}
            new_data = updater(existing_data)
            f.seek(0)
            f.truncate()
            json.dump(new_data, f, ensure_ascii=False, indent=2)
            return new_data
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_glossary(novel_name: str) -> dict[str, str]:
    """Load term glossary for a novel. Returns empty dict if not found."""
    path = _glossary_path(novel_name)
    data = _read_json_locked(path)
    return data.get("terms", {})


def load_source_language(novel_name: str) -> str:
    """Load detected source language for a novel. Returns empty string if not found."""
    path = _glossary_path(novel_name)
    data = _read_json_locked(path)
    return data.get("source_language", "")


def save_source_language(novel_name: str, language: str):
    """Save detected source language for a novel (thread-safe)."""
    if not language:
        return
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "source_language": language,
    })


def save_glossary(novel_name: str, terms: dict[str, str]):
    """Save/merge terms into the novel's glossary (thread-safe)."""
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "terms": {**data.get("terms", {}), **terms},
    })


def load_chapter_summary(novel_name: str, chapter_number: int) -> str:
    """Load summary for a specific chapter. Returns empty string if not found."""
    path = _glossary_path(novel_name)
    data = _read_json_locked(path)
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
    data = _read_json_locked(path)
    summaries = data.get("chapter_summaries", {})

    parts = []
    for ch in range(current_chapter - 1, max(0, current_chapter - 1 - max_count), -1):
        summary = summaries.get(str(ch), "")
        if summary:
            parts.append(f"Chapter {ch}: {summary}")

    if not parts:
        return ""

    parts.reverse()
    return "\n\n".join(parts)


def save_chapter_summary(novel_name: str, chapter_number: int, summary: str):
    """Save a chapter summary (thread-safe)."""
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "chapter_summaries": {**data.get("chapter_summaries", {}), str(chapter_number): summary},
    })


def format_glossary_for_prompt(terms: dict[str, str]) -> str:
    """Format glossary as a string for inclusion in LLM prompts."""
    if not terms:
        return ""
    lines = ["=== GLOSSARY (use these translations consistently) ==="]
    for original, translated in terms.items():
        lines.append(f"  {original} → {translated}")
    lines.append("=== END GLOSSARY ===")
    return "\n".join(lines)


def load_translated_chapters(novel_name: str) -> set[int]:
    """Load set of translated chapter numbers for a novel."""
    path = _glossary_path(novel_name)
    data = _read_json_locked(path)
    chapters = data.get("translated_chapters", [])
    return set(chapters)


def mark_chapter_translated(novel_name: str, chapter_number: int):
    """Mark a chapter as translated (thread-safe)."""
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "translated_chapters": sorted(set(data.get("translated_chapters", [])) | {chapter_number}),
    })
