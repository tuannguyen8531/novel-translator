"""
Glossary Service — JSON-based per-novel glossary management.

Each novel gets its own glossary file at glossary/{novel_name}.json.
Structure:
{
    "terms": {
        "原始术语": "Bản dịch tiếng Việt",
        "李明": "Lý Minh"
    },
    "source_language": "chinese",
    "entities": {
        "李明": {"name_vi": "Lý Minh", "role": "protagonist"}
    },
    "edges": [
        ["李明", "张伟", "friend", 3]
    ],
    "chapter_summaries": {
        "1": "Summary of chapter 1...",
        "2": "Summary of chapter 2..."
    }
}

Character schema:
- entities: dict of original_name -> {name_vi, role, pronoun}
  role: protagonist | antagonist | supporting | minor
  pronoun: Vietnamese pronoun assigned on first appearance (immutable)
- edges: list of [from_orig, to_orig, relationship_type, since_chapter]
  Each relationship stored ONCE (no bidirectional duplication).
  Relationship types: mother, father, sibling, friend, enemy, master,
  disciple, rival, classmate, teacher, romantic interest, etc.
"""

import fcntl
import json
from pathlib import Path

from src.domain.glossary import (
    format_recent_summaries,
    merge_character_context,
    merge_pronoun_examples,
    select_active_character_context,
    upsert_relationship,
    validate_glossary_data,
)

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


def load_glossary_data(novel_name: str) -> dict:
    """Load the full glossary JSON data for a novel."""
    return _read_json_locked(_glossary_path(novel_name))


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


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------

def load_glossary(novel_name: str) -> dict[str, str]:
    """Load term glossary for a novel. Returns empty dict if not found."""
    path = _glossary_path(novel_name)
    data = _read_json_locked(path)
    return data.get("terms", {})


def save_glossary(novel_name: str, terms: dict[str, str]):
    """Save/merge terms into the novel's glossary (thread-safe)."""
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "terms": {**data.get("terms", {}), **terms},
    })


def remove_glossary_term(novel_name: str, original: str) -> bool:
    """Remove a glossary term. Returns True if the term existed."""
    path = _glossary_path(novel_name)
    removed = False

    def updater(data: dict) -> dict:
        nonlocal removed
        terms = dict(data.get("terms", {}))
        removed = original in terms
        terms.pop(original, None)
        return {**data, "terms": terms}

    _merge_json_locked(path, updater)
    return removed


def save_character_pronoun(novel_name: str, original_name: str, pronoun: str) -> bool:
    """Set a character pronoun. Returns True if the character existed."""
    path = _glossary_path(novel_name)
    found = False

    def updater(data: dict) -> dict:
        nonlocal found
        entities = dict(data.get("entities", {}))
        if original_name not in entities:
            return data
        info = dict(entities[original_name])
        info["pronoun"] = pronoun
        entities[original_name] = info
        found = True
        return {**data, "entities": entities}

    _merge_json_locked(path, updater)
    return found


def save_character(novel_name: str, original_name: str, name_vi: str = "", role: str = "") -> bool:
    """Update a character's Vietnamese name and/or role. Returns True if found."""
    path = _glossary_path(novel_name)
    found = False

    def updater(data: dict) -> dict:
        nonlocal found
        entities = dict(data.get("entities", {}))
        if original_name not in entities:
            return data
        info = dict(entities[original_name])
        if name_vi:
            info["name_vi"] = name_vi
        if role:
            info["role"] = role
        entities[original_name] = info
        found = True
        return {**data, "entities": entities}

    _merge_json_locked(path, updater)
    return found


def save_relationship(
    novel_name: str,
    from_char: str,
    to_char: str,
    relationship: str,
    since_chapter: int | None = None,
) -> bool:
    """Add or update a relationship. Returns True when both characters exist."""
    path = _glossary_path(novel_name)
    updated = False

    def updater(data: dict) -> dict:
        nonlocal updated
        entities = data.get("entities", {})
        if from_char not in entities or to_char not in entities:
            return data
        updated = True
        return upsert_relationship(data, from_char, to_char, relationship, since_chapter=since_chapter)

    _merge_json_locked(path, updater)
    return updated


def validate_glossary(novel_name: str) -> list[str]:
    """Validate a novel glossary file and return issues."""
    return validate_glossary_data(load_glossary_data(novel_name))


# ---------------------------------------------------------------------------
# Source language
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Chapter summaries
# ---------------------------------------------------------------------------

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

    return format_recent_summaries(summaries, current_chapter, max_count=max_count)


def save_chapter_summary(novel_name: str, chapter_number: int, summary: str):
    """Save a chapter summary (thread-safe)."""
    path = _glossary_path(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "chapter_summaries": {**data.get("chapter_summaries", {}), str(chapter_number): summary},
    })


# ---------------------------------------------------------------------------
# Characters — Entity + Edge graph
# ---------------------------------------------------------------------------

def get_active_context(novel_name: str, source_text: str) -> tuple[dict, list]:
    """Load only characters and relationships relevant to the current source text.

    Algorithm:
        1. Scan source_text for known character names (active set) using boundary-aware matching.
        2. Collect edges where at least one endpoint is in the active set (F1 neighbors).
        3. Build entity dict for active + F1 characters.

    Returns:
        (entities, edges) — both filtered to active context only.
        entities: {orig_name: {"name_vi": str, "role": str}}
        edges:    [[from, to, rel_type, since_chapter], ...]
    """
    data = _read_json_locked(_glossary_path(novel_name))
    all_entities: dict = data.get("entities", {})
    all_edges: list = data.get("edges", [])

    if not all_entities:
        return {}, []

    return select_active_character_context(all_entities, all_edges, source_text)


def save_characters_batch(novel_name: str, entities: dict, edges: list, chapter: int = 0):
    """Save character entities and relationship edges (thread-safe).

    Args:
        entities: {orig_name: {"name_vi": str, "role": str}}
        edges:    [[from, to, rel_type]] or [[from, to, rel_type, since_chapter]]
                  Each relationship should be stored ONCE (no bidirectional duplicates).
        chapter:  Current chapter number (used as since_chapter fallback).
    """
    if not entities and not edges:
        return

    path = _glossary_path(novel_name)

    def updater(data: dict) -> dict:
        return merge_character_context(data, entities, edges, chapter=chapter)

    _merge_json_locked(path, updater)


# ---------------------------------------------------------------------------
# Pronoun usage examples
# ---------------------------------------------------------------------------

def load_pronoun_examples(novel_name: str) -> dict[str, list[str]]:
    """Load pronoun usage examples for a novel."""
    data = _read_json_locked(_glossary_path(novel_name))
    return data.get("pronoun_examples", {})


def save_pronoun_examples(novel_name: str, examples: dict[str, list[str]]) -> None:
    """Merge and save pronoun usage examples (thread-safe)."""
    if not examples:
        return
    path = _glossary_path(novel_name)

    def updater(data: dict) -> dict:
        existing = data.get("pronoun_examples", {})
        merged = merge_pronoun_examples(existing, examples)
        return {**data, "pronoun_examples": merged}

    _merge_json_locked(path, updater)
