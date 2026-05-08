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
- entities: dict of original_name -> {name_vi, role}
  role: protagonist | antagonist | supporting | minor
- edges: list of [from_orig, to_orig, relationship_type, since_chapter]
  Each relationship stored ONCE (no bidirectional duplication).
  Relationship types: mother, father, sibling, friend, enemy, master,
  disciple, rival, classmate, teacher, romantic interest, etc.
"""

import fcntl
import json
import re
from pathlib import Path

CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]')

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


def format_glossary_for_prompt(terms: dict[str, str]) -> str:
    """Format glossary as a string for inclusion in LLM prompts."""
    if not terms:
        return ""
    lines = ["=== GLOSSARY (use these translations consistently) ==="]
    for original, translated in terms.items():
        lines.append(f"  {original} → {translated}")
    lines.append("=== END GLOSSARY ===")
    return "\n".join(lines)


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


# ---------------------------------------------------------------------------
# Characters — Entity + Edge graph
# ---------------------------------------------------------------------------

def _is_name_boundary(text: str, pos: int) -> bool:
    """Check if position is a valid CJK/word boundary (not inside a longer word)."""
    if pos < 0 or pos >= len(text):
        return True
    return not CJK_RE.match(text[pos]) and not text[pos].isalnum()


def _find_name_in_text(name: str, source_text: str) -> bool:
    """Check if name appears in text with proper boundaries (no substring false positives)."""
    escaped = re.escape(name)
    for m in re.finditer(escaped, source_text):
        if _is_name_boundary(source_text, m.start() - 1) and _is_name_boundary(source_text, m.end()):
            return True
    return False


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

    # Step 1: find which characters appear in source text (boundary-aware)
    active_names = {name for name in all_entities if _find_name_in_text(name, source_text)}

    if not active_names:
        return {}, []

    # Step 2: collect relevant edges + F1 neighbors
    f1_names: set[str] = set()
    active_edges: list = []
    for edge in all_edges:
        if len(edge) < 3:
            continue
        from_char, to_char = edge[0], edge[1]
        if from_char in active_names or to_char in active_names:
            active_edges.append(edge)
            f1_names.add(from_char)
            f1_names.add(to_char)

    # Step 3: build filtered entity map (active + F1)
    all_relevant = active_names | f1_names
    active_entities = {
        name: all_entities[name]
        for name in all_relevant
        if name in all_entities
    }

    return active_entities, active_edges


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

    # Normalize edges to 4-element lists
    tagged_edges = []
    for edge in edges:
        if len(edge) >= 3:
            since = edge[3] if len(edge) > 3 else chapter
            tagged_edges.append([edge[0], edge[1], edge[2], since])

    path = _glossary_path(novel_name)

    def updater(data: dict) -> dict:
        # --- Merge entities ---
        existing_entities: dict = data.get("entities", {})
        for name, info in entities.items():
            if name not in existing_entities:
                existing_entities[name] = {
                    "name_vi": info.get("name_vi", ""),
                    "role": info.get("role", "unknown"),
                }
            else:
                if info.get("name_vi"):
                    existing_entities[name]["name_vi"] = info["name_vi"]
                new_role = info.get("role", "")
                if new_role and new_role != "unknown":
                    existing_entities[name]["role"] = new_role

        # --- Merge edges (deduplication: treat A→B and B→A as same pair) ---
        existing_edges: list = data.get("edges", [])
        # Build index of seen pairs (canonical order doesn't matter; track both)
        seen_pairs: set[tuple] = set()
        for e in existing_edges:
            if len(e) >= 2:
                seen_pairs.add((e[0], e[1]))
                seen_pairs.add((e[1], e[0]))  # treat reverse as duplicate

        for edge in tagged_edges:
            from_char, to_char, rel_type, since = edge
            if (from_char, to_char) in seen_pairs:
                # Update type on the existing forward edge if found
                for e in existing_edges:
                    if e[0] == from_char and e[1] == to_char:
                        e[2] = rel_type
                        break
            else:
                # Truly new relationship
                existing_edges.append([from_char, to_char, rel_type, since])
                seen_pairs.add((from_char, to_char))
                seen_pairs.add((to_char, from_char))

        return {**data, "entities": existing_entities, "edges": existing_edges}

    _merge_json_locked(path, updater)


def format_relationships_shorthand(entities: dict, edges: list) -> str:
    """Format active character context as compact shorthand for LLM prompts.

    Outputs:
        === CHARACTERS ===
        Roles: Lục Viễn Thu[protagonist], Bạch Thanh Hạ[protagonist]
        Relations: Tô Tiểu Nhã(mother)->Lục Viễn Thu; Lục Thiên(father)->Lục Viễn Thu
        === END CHARACTERS ===
    """
    if not entities:
        return ""

    # Build roles line (skip minor/unknown to save tokens)
    NOTABLE_ROLES = {"protagonist", "antagonist", "supporting"}
    roles_parts = []
    for name, info in entities.items():
        name_vi = info.get("name_vi") or name
        role = info.get("role", "")
        if role in NOTABLE_ROLES:
            roles_parts.append(f"{name_vi}[{role}]")

    # Build relations line
    rel_parts = []
    for edge in edges:
        if len(edge) < 3:
            continue
        from_char, to_char, rel_type = edge[0], edge[1], edge[2]
        from_vi = entities.get(from_char, {}).get("name_vi") or from_char
        to_vi = entities.get(to_char, {}).get("name_vi") or to_char
        rel_parts.append(f"{from_vi}({rel_type})->{to_vi}")

    lines = ["=== CHARACTERS ==="]
    if roles_parts:
        lines.append("Roles: " + ", ".join(roles_parts))
    if rel_parts:
        lines.append("Relations: " + "; ".join(rel_parts))
    lines.append("=== END CHARACTERS ===")

    return "\n".join(lines)
