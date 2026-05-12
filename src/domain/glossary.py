"""Domain rules for glossary, chapter memory, and character context."""

import re


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
