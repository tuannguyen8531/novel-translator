"""Domain rules for glossary, chapter memory, and character context."""

import re

MAX_PRONOUN_EXAMPLES_PER_CHAR = 3
MAX_PRONOUN_EXAMPLE_LENGTH = 150


CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]")


def format_glossary_for_prompt(terms: dict[str, str]) -> str:
    """Format glossary terms for inclusion in LLM prompts."""
    if not terms:
        return ""
    lines = ["=== GLOSSARY (use these translations consistently) ==="]
    for original, translated in terms.items():
        lines.append(f"  {original} → {translated}")
    lines.append("=== END GLOSSARY ===")
    return "\n".join(lines)


def validate_glossary_data(data: dict) -> list[str]:
    """Validate glossary JSON shape and return human-readable issues."""
    issues: list[str] = []

    if not isinstance(data, dict):
        return ["glossary root must be an object"]

    terms = data.get("terms", {})
    if terms is not None and not isinstance(terms, dict):
        issues.append("terms must be an object")
    elif isinstance(terms, dict):
        for original, translated in terms.items():
            if not isinstance(original, str) or not original.strip():
                issues.append("terms contains an empty or non-string source term")
            if not isinstance(translated, str) or not translated.strip():
                issues.append(f"term {original!r} has an empty or non-string translation")

    source_language = data.get("source_language", "")
    if source_language is not None and not isinstance(source_language, str):
        issues.append("source_language must be a string")

    entities = data.get("entities", {})
    if entities is not None and not isinstance(entities, dict):
        issues.append("entities must be an object")
        entities = {}
    elif isinstance(entities, dict):
        for original, info in entities.items():
            if not isinstance(original, str) or not original.strip():
                issues.append("entities contains an empty or non-string original name")
                continue
            if not isinstance(info, dict):
                issues.append(f"entity {original!r} must be an object")
                continue
            for key in ("name_vi", "role", "pronoun"):
                if key in info and not isinstance(info[key], str):
                    issues.append(f"entity {original!r}.{key} must be a string")

    edges = data.get("edges", [])
    if edges is not None and not isinstance(edges, list):
        issues.append("edges must be a list")
    elif isinstance(edges, list):
        entity_names = set(entities) if isinstance(entities, dict) else set()
        for index, edge in enumerate(edges):
            if not isinstance(edge, list) or len(edge) < 3:
                issues.append(f"edge {index} must be [from, to, relationship, since_chapter?]")
                continue
            from_char, to_char, relationship = edge[0], edge[1], edge[2]
            if not isinstance(from_char, str) or not from_char.strip():
                issues.append(f"edge {index} has an invalid from character")
            if not isinstance(to_char, str) or not to_char.strip():
                issues.append(f"edge {index} has an invalid to character")
            if not isinstance(relationship, str) or not relationship.strip():
                issues.append(f"edge {index} has an invalid relationship")
            if len(edge) > 3 and not isinstance(edge[3], int):
                issues.append(f"edge {index} since_chapter must be an integer")
            if entity_names:
                if isinstance(from_char, str) and from_char not in entity_names:
                    issues.append(f"edge {index} references unknown character {from_char!r}")
                if isinstance(to_char, str) and to_char not in entity_names:
                    issues.append(f"edge {index} references unknown character {to_char!r}")

    summaries = data.get("chapter_summaries", {})
    if summaries is not None and not isinstance(summaries, dict):
        issues.append("chapter_summaries must be an object")
    elif isinstance(summaries, dict):
        for chapter, summary in summaries.items():
            if not isinstance(chapter, str) or not chapter.isdigit():
                issues.append(f"chapter summary key {chapter!r} must be a numeric string")
            if not isinstance(summary, str):
                issues.append(f"chapter summary {chapter!r} must be a string")

    pronoun_examples = data.get("pronoun_examples", {})
    if pronoun_examples is not None and not isinstance(pronoun_examples, dict):
        issues.append("pronoun_examples must be an object")
    elif isinstance(pronoun_examples, dict):
        for name, examples in pronoun_examples.items():
            if not isinstance(name, str) or not name.strip():
                issues.append("pronoun_examples contains an empty or non-string character name")
            if not isinstance(examples, list):
                issues.append(f"pronoun_examples[{name!r}] must be a list")
            else:
                for i, ex in enumerate(examples):
                    if not isinstance(ex, str) or not ex.strip():
                        issues.append(f"pronoun_examples[{name!r}][{i}] must be a non-empty string")

    return issues


def audit_term_usage(terms: dict[str, str], source_text: str, translated_text: str) -> list[dict]:
    """Find glossary terms that look inconsistent between source and translation."""
    issues: list[dict] = []
    for original, translated in sorted(terms.items()):
        if not original or not translated or original not in source_text:
            continue
        if translated not in translated_text:
            issues.append({
                "term": original,
                "expected": translated,
                "issue": "missing_translation",
            })
        if original in translated_text:
            issues.append({
                "term": original,
                "expected": translated,
                "issue": "source_term_leaked",
            })
    return issues


def format_recent_summaries(summaries: dict, current_chapter: int, max_count: int = 3) -> str:
    """Format the most recent chapter summaries before current_chapter."""
    parts = []
    for ch in range(current_chapter - 1, max(0, current_chapter - 1 - max_count), -1):
        summary = summaries.get(str(ch), "")
        if summary:
            parts.append(f"Chapter {ch}: {summary}")

    if not parts:
        return ""

    parts.reverse()
    return "\n\n".join(parts)


def _is_name_boundary(text: str, pos: int) -> bool:
    """Check if position is a valid CJK/word boundary, not inside a longer word."""
    if pos < 0 or pos >= len(text):
        return True
    return not CJK_RE.match(text[pos]) and not text[pos].isalnum()


def find_name_in_text(name: str, source_text: str) -> bool:
    """Check if name appears in text with proper boundaries."""
    escaped = re.escape(name)
    for match in re.finditer(escaped, source_text):
        if _is_name_boundary(source_text, match.start() - 1) and _is_name_boundary(source_text, match.end()):
            return True
    return False


def select_active_character_context(all_entities: dict, all_edges: list, source_text: str) -> tuple[dict, list]:
    """Select active characters and first-degree relationships for the current source text."""
    if not all_entities:
        return {}, []

    active_names = {name for name in all_entities if find_name_in_text(name, source_text)}

    if not active_names:
        return {}, []

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

    all_relevant = active_names | f1_names
    active_entities = {
        name: all_entities[name]
        for name in all_relevant
        if name in all_entities
    }

    return active_entities, active_edges


def merge_character_context(data: dict, entities: dict, edges: list, chapter: int = 0) -> dict:
    """Merge character entities and relationship edges into glossary data."""
    existing_entities: dict = data.get("entities", {})
    for name, info in entities.items():
        if name not in existing_entities:
            existing_entities[name] = {
                "name_vi": info.get("name_vi", ""),
                "role": info.get("role", "unknown"),
                "pronoun": info.get("pronoun", ""),
            }
        else:
            if info.get("name_vi"):
                existing_entities[name]["name_vi"] = info["name_vi"]
            new_role = info.get("role", "")
            if new_role and new_role != "unknown":
                existing_entities[name]["role"] = new_role
            if not existing_entities[name].get("pronoun"):
                existing_entities[name]["pronoun"] = info.get("pronoun", "")

    tagged_edges = []
    for edge in edges:
        if len(edge) >= 3:
            since = edge[3] if len(edge) > 3 else chapter
            tagged_edges.append([edge[0], edge[1], edge[2], since])

    existing_edges: list = data.get("edges", [])
    seen_pairs: set[tuple] = set()
    for edge in existing_edges:
        if len(edge) >= 2:
            seen_pairs.add((edge[0], edge[1]))
            seen_pairs.add((edge[1], edge[0]))

    for edge in tagged_edges:
        from_char, to_char, rel_type, since = edge
        if (from_char, to_char) in seen_pairs:
            for existing_edge in existing_edges:
                if existing_edge[0] == from_char and existing_edge[1] == to_char:
                    existing_edge[2] = rel_type
                    break
        else:
            existing_edges.append([from_char, to_char, rel_type, since])
            seen_pairs.add((from_char, to_char))
            seen_pairs.add((to_char, from_char))

    return {**data, "entities": existing_entities, "edges": existing_edges}


def upsert_relationship(
    data: dict,
    from_char: str,
    to_char: str,
    relationship: str,
    since_chapter: int | None = None,
) -> dict:
    """Add or update one relationship edge, preserving the one-edge-per-pair rule."""
    edges = [list(edge) for edge in data.get("edges", [])]
    for edge in edges:
        if len(edge) >= 3 and {edge[0], edge[1]} == {from_char, to_char}:
            edge[0] = from_char
            edge[1] = to_char
            edge[2] = relationship
            if since_chapter is None:
                return {**data, "edges": edges}
            if len(edge) > 3:
                edge[3] = since_chapter
            else:
                edge.append(since_chapter)
            return {**data, "edges": edges}

    edge = [from_char, to_char, relationship]
    if since_chapter is not None:
        edge.append(since_chapter)
    edges.append(edge)
    return {**data, "edges": edges}


def format_relationships_shorthand(entities: dict, edges: list) -> str:
    """Format active character context as compact shorthand for LLM prompts."""
    if not entities:
        return ""

    notable_roles = {"protagonist", "antagonist", "supporting"}
    roles_parts = []
    for name, info in entities.items():
        name_vi = info.get("name_vi") or name
        role = info.get("role", "")
        pronoun = info.get("pronoun", "")
        if role in notable_roles or pronoun:
            tag = role
            if pronoun:
                tag += f', pronoun="{pronoun}"'
            roles_parts.append(f"{name_vi}[{tag}]")
        elif role:
            roles_parts.append(f"{name_vi}[{role}]")

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


def extract_pronoun_examples(translation: str, entities: dict) -> dict[str, list[str]]:
    """Extract sentences showing pronoun usage for each character from translation.

    For each character with a pronoun, finds sentences where the pronoun is used.
    Returns at most MAX_PRONOUN_EXAMPLES_PER_CHAR examples per character.
    """
    sentences = re.split(r"(?<=[.!?…])\s+", translation)
    examples: dict[str, list[str]] = {}

    for name, info in entities.items():
        pronoun = info.get("pronoun", "")
        name_vi = info.get("name_vi", "")
        if not pronoun or not name_vi:
            continue

        char_examples = []
        pronoun_lower = pronoun.lower()

        for sentence in sentences:
            if len(char_examples) >= MAX_PRONOUN_EXAMPLES_PER_CHAR:
                break
            if len(sentence) > MAX_PRONOUN_EXAMPLE_LENGTH:
                continue
            sentence_lower = sentence.lower()
            # Use word boundaries to avoid partial matches (e.g. 'y' matching 'máy')
            if re.search(rf'\b{re.escape(pronoun_lower)}\b', sentence_lower):
                char_examples.append(sentence.strip())

        if char_examples:
            examples[name] = char_examples

    return examples


def merge_pronoun_examples(existing: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, list[str]]:
    """Merge new pronoun examples into existing, deduplicating and keeping recent ones."""
    merged = dict(existing)
    for name, new_examples in new.items():
        existing_examples = merged.get(name, [])
        # Add new examples that aren't already present
        for ex in new_examples:
            if ex not in existing_examples:
                existing_examples.append(ex)
        # Keep only the most recent examples (last N)
        merged[name] = existing_examples[-MAX_PRONOUN_EXAMPLES_PER_CHAR:]
    return merged


def format_pronoun_examples(entities: dict, pronoun_examples: dict[str, list[str]]) -> str:
    """Format pronoun usage examples for inclusion in translator prompt."""
    if not pronoun_examples:
        return ""

    parts = ["=== PRONOUN USAGE (follow these patterns consistently) ==="]
    for name, info in entities.items():
        if name not in pronoun_examples:
            continue
        name_vi = info.get("name_vi") or name
        pronoun = info.get("pronoun", "")
        if not pronoun:
            continue

        parts.append(f'{name_vi} → use "{pronoun}" as third-person pronoun:')
        for example in pronoun_examples[name]:
            parts.append(f'  - "{example}"')

    parts.append("=== END PRONOUN USAGE ===")
    return "\n".join(parts)
