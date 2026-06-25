"""
Glossary Service — JSON-based per-novel glossary management.

Each novel gets its own glossary file at glossary/{novel_name}.json.
Structure:
{
    "terms": {
        "原始术语": "Target-language translation",
        "李明": "Lý Minh"
    },
    "source_language": "chinese",
    "entities": {
        "李明": {"translated_name": "Lý Minh", "role": "protagonist"}
    },
    "edges": [
        ["李明", "张伟", "friend", 3]
    ],
    "chapter_summaries": {
        "1": "Summary of chapter 1...",
        "2": "Summary of chapter 2..."
    }
}

If NOVEL_SHARE_DIR is set, also checks {share_dir}/{novel}/glossary.json
or glossary.{target}.json as a fallback source. If found in share dir, copies
to project glossary.

Character schema:
- entities: dict of original_name -> {translated_name, role, pronoun, aliases?}
  role: protagonist | antagonist | supporting | minor
  pronoun: target-language pronoun/reference style assigned on first appearance (immutable)
  aliases: source-language short/full-name variants resolved to the canonical entity
- edges: list of [from_orig, to_orig, relationship_type, since_chapter]
  Each relationship stored ONCE (no bidirectional duplication).
  Relationship types: mother, father, sibling, friend, enemy, master,
  disciple, rival, classmate, teacher, romantic interest, etc.
- address_rules: list of {speaker, listener, self, other, since, until?, notes?}
  Non-overlapping per-pair direct address/reference timelines in the target language.
"""

import fcntl
import shutil
import json
from collections.abc import Callable
from pathlib import Path

from src.config import config
from src.domain.target_language import normalize_target_language
from src.domain.glossary import (
    format_recent_summaries,
    merge_character_context,
    normalize_character_info,
    normalize_glossary_data,
    select_active_address_rules,
    select_active_character_context,
    upsert_relationship,
    validate_glossary_data,
)

GLOSSARY_DIR = Path("glossary")


def _current_target_language() -> str:
    target = getattr(config, "target_language", "vi")
    if not isinstance(target, str):
        return "vi"
    return normalize_target_language(target)


def _glossary_path(novel_name: str) -> Path:
    """Get path to glossary file for a novel (always in project glossary/)."""
    target = _current_target_language()
    if target == "vi":
        return GLOSSARY_DIR / f"{novel_name}.json"
    return GLOSSARY_DIR / f"{novel_name}.{target}.json"


def _share_glossary_path(novel_name: str) -> Path | None:
    """Get path to glossary file in share dir, if configured."""
    if not config.novel_share_dir:
        return None
    target = _current_target_language()
    if target == "vi":
        return Path(config.novel_share_dir) / novel_name / "glossary.json"
    return Path(config.novel_share_dir) / novel_name / f"glossary.{target}.json"


def _resolve_glossary(novel_name: str) -> Path:
    """Resolve glossary path with share dir fallback.

    Priority:
    1. Project glossary/{novel_name}.json or glossary/{novel_name}.{target}.json
    2. Share dir {NOVEL_SHARE_DIR}/{novel}/glossary*.json (copies to project if found)
    3. Returns project path (will be created on first save)
    """
    project_path = _glossary_path(novel_name)
    if project_path.exists():
        return project_path

    share_path = _share_glossary_path(novel_name)
    if share_path and share_path.exists():
        project_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(share_path, project_path)
        return project_path

    return project_path


def _ensure_dir(path: Path | None = None):
    """Create glossary directory if it doesn't exist."""
    if path is None:
        GLOSSARY_DIR.mkdir(parents=True, exist_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)


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
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_glossary_data(novel_name: str) -> dict:
    """Load the full glossary JSON data for a novel."""
    return _read_json_locked(_resolve_glossary(novel_name))


def _merge_json_locked(path: Path, updater: Callable[[dict], dict]) -> dict:
    """Atomically read-modify-write JSON with exclusive lock.

    After writing to the project path, copies to share dir if configured.

    Args:
        path: File path
        updater: Function that takes existing data dict and returns updated dict
    """
    _ensure_dir(path)
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
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # Sync to share dir after successful write
    _sync_to_share(path, new_data)

    return new_data


def _sync_to_share(project_path: Path, data: dict) -> None:
    """Copy glossary data to share dir if configured."""
    if not config.novel_share_dir:
        return

    # Extract novel name from filename: "my-novel.json" or "my-novel.en.json".
    target = _current_target_language()
    suffix = f".{target}.json"
    if target != "vi" and project_path.name.endswith(suffix):
        novel_name = project_path.name[:-len(suffix)]
    else:
        novel_name = project_path.stem
    share_dir = Path(config.novel_share_dir) / novel_name
    share_path = share_dir / "glossary.json" if target == "vi" else share_dir / f"glossary.{target}.json"

    if not share_path.exists() or share_path.resolve() != project_path.resolve():
        share_dir.mkdir(parents=True, exist_ok=True)
        share_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------

def load_glossary(novel_name: str) -> dict[str, str]:
    """Load term glossary for a novel. Returns empty dict if not found."""
    path = _resolve_glossary(novel_name)
    data = _read_json_locked(path)
    return data.get("terms", {})


def save_glossary(novel_name: str, terms: dict[str, str]):
    """Save/merge terms into the novel's glossary (thread-safe)."""
    path = _resolve_glossary(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "terms": {**data.get("terms", {}), **terms},
    })


def remove_glossary_term(novel_name: str, original: str) -> bool:
    """Remove a glossary term. Returns True if the term existed."""
    path = _resolve_glossary(novel_name)
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
    path = _resolve_glossary(novel_name)
    found = False

    def updater(data: dict) -> dict:
        nonlocal found
        entities = dict(data.get("entities", {}))
        if original_name not in entities:
            return data
        info = normalize_character_info(dict(entities[original_name]))
        info["pronoun"] = pronoun
        entities[original_name] = info
        found = True
        return {**data, "entities": entities}

    _merge_json_locked(path, updater)
    return found


def save_character(
    novel_name: str,
    original_name: str,
    translated_name: str = "",
    role: str = "",
    name_vi: str = "",
) -> bool:
    """Update a character's translated name and/or role. Returns True if found."""
    path = _resolve_glossary(novel_name)
    found = False
    name_value = translated_name or name_vi

    def updater(data: dict) -> dict:
        nonlocal found
        entities = dict(data.get("entities", {}))
        if original_name not in entities:
            return data
        info = normalize_character_info(dict(entities[original_name]))
        if name_value:
            info["translated_name"] = name_value
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
    path = _resolve_glossary(novel_name)
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


def clean_glossary(novel_name: str) -> dict:
    """Normalize a glossary file and return before/after counts."""
    path = _resolve_glossary(novel_name)

    stats: dict = {}

    def updater(data: dict) -> dict:
        nonlocal stats
        before_edges = len(data.get("edges", []))
        before_address_rules = len(data.get("address_rules", []))
        before_pronoun_examples = len(data.get("pronoun_examples", {}))
        cleaned = normalize_glossary_data(data)
        stats = {
            "entities": len(cleaned.get("entities", {})),
            "edges_before": before_edges,
            "edges_after": len(cleaned.get("edges", [])),
            "address_rules_before": before_address_rules,
            "address_rules_after": len(cleaned.get("address_rules", [])),
            "pronoun_examples_removed": before_pronoun_examples,
        }
        return cleaned

    _merge_json_locked(path, updater)
    return stats


# ---------------------------------------------------------------------------
# Source language
# ---------------------------------------------------------------------------

def load_source_language(novel_name: str) -> str:
    """Load detected source language for a novel. Returns empty string if not found."""
    path = _resolve_glossary(novel_name)
    data = _read_json_locked(path)
    return data.get("source_language", "")


def save_source_language(novel_name: str, language: str):
    """Save detected source language for a novel (thread-safe)."""
    if not language:
        return
    path = _resolve_glossary(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "source_language": language,
    })


# ---------------------------------------------------------------------------
# Chapter summaries
# ---------------------------------------------------------------------------

def load_chapter_summary(novel_name: str, chapter_number: int) -> str:
    """Load summary for a specific chapter. Returns empty string if not found."""
    path = _resolve_glossary(novel_name)
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
    path = _resolve_glossary(novel_name)
    data = _read_json_locked(path)
    summaries = data.get("chapter_summaries", {})

    return format_recent_summaries(summaries, current_chapter, max_count=max_count)


def save_chapter_summary(novel_name: str, chapter_number: int, summary: str):
    """Save a chapter summary (thread-safe)."""
    path = _resolve_glossary(novel_name)
    _merge_json_locked(path, lambda data: {
        **data,
        "chapter_summaries": {**data.get("chapter_summaries", {}), str(chapter_number): summary},
    })


# ---------------------------------------------------------------------------
# Characters — Entity + Edge graph
# ---------------------------------------------------------------------------

def get_active_context(novel_name: str, source_text: str, chapter_number: int = 0) -> tuple[dict, list, list]:
    """Load only characters and relationships relevant to the current source text.

    Algorithm:
        1. Scan source_text for known character names (active set) using boundary-aware matching.
        2. Collect only pair edges where both endpoints are in the active set.
        3. Build entity dict for directly active characters.

    Returns:
        (entities, edges, address_rules) — filtered to active context only.
        entities: {orig_name: {"translated_name": str, "role": str}}
        edges:    [[from, to, rel_type, since_chapter], ...]
        address_rules: [{speaker, listener, self, other, since, until?, notes?}, ...]
    """
    data = normalize_glossary_data(_read_json_locked(_resolve_glossary(novel_name)))
    all_entities: dict = data.get("entities", {})
    all_edges: list = data.get("edges", [])
    all_address_rules: list = data.get("address_rules", [])

    if not all_entities:
        return {}, [], []

    entities, edges = select_active_character_context(all_entities, all_edges, source_text)
    address_rules = select_active_address_rules(all_address_rules, entities, chapter_number)
    return entities, edges, address_rules


def save_characters_batch(
    novel_name: str,
    entities: dict,
    edges: list,
    address_rules: list | None = None,
    chapter: int = 0,
):
    """Save character entities and relationship edges (thread-safe).

    Args:
        entities: {orig_name: {"translated_name": str, "role": str}}
        edges:    [[from, to, rel_type]] or [[from, to, rel_type, since_chapter]]
                  Each relationship should be stored ONCE (no bidirectional duplicates).
        address_rules: Direct address/reference rules for character pairs.
        chapter:  Current chapter number (used as since_chapter fallback).
    """
    if not entities and not edges and not address_rules:
        return

    path = _resolve_glossary(novel_name)

    def updater(data: dict) -> dict:
        return merge_character_context(data, entities, edges, address_rules=address_rules, chapter=chapter)

    _merge_json_locked(path, updater)
