"""Domain rules for glossary, chapter memory, and character context."""

import re


CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]")

SYMMETRIC_RELATIONSHIPS = {
    "spouse", "romantic interest", "ex", "friend", "enemy", "rival", "ally",
    "sibling", "half-sibling", "classmate", "colleague", "acquaintance",
    "neighbor", "relative", "cousin",
}

INVERSE_RELATIONSHIPS = {
    "mother": "child",
    "father": "child",
    "parent": "child",
    "son": "parent",
    "daughter": "parent",
    "child": "parent",
    "brother": "sibling",
    "sister": "sibling",
    "husband": "wife",
    "wife": "husband",
    "master": "disciple",
    "disciple": "master",
    "teacher": "student",
    "student": "teacher",
    "servant": "employer",
    "employer": "employee",
    "boss": "employee",
    "employee": "boss",
    "grandparent": "grandchild",
    "grandchild": "grandparent",
    "adoptive parent": "adoptive child",
    "adoptive child": "adoptive parent",
    "step-parent": "step-child",
    "step-child": "step-parent",
    "mentor": "ward",
    "guardian": "ward",
    "ward": "guardian",
    "protector": "ward",
}


def get_character_translated_name(info: dict) -> str:
    """Return the target-language character name, accepting legacy name_vi."""
    return info.get("translated_name") or info.get("name_vi") or ""


def normalize_character_info(info: dict) -> dict:
    """Normalize a character entity to the current glossary schema."""
    aliases = info.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = []
    normalized = {
        "translated_name": get_character_translated_name(info),
        "role": info.get("role", "unknown"),
        "pronoun": info.get("pronoun", ""),
    }
    normalized_aliases = list(dict.fromkeys(
        alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip()
    ))
    if normalized_aliases:
        normalized["aliases"] = normalized_aliases
    return normalized


def _name_tokens(name: str) -> list[str]:
    return [token.casefold() for token in re.split(r"[\s._-]+", name.strip()) if token]


def _is_expanded_name(short_name: str, long_name: str) -> bool:
    """Return whether long_name is a clear token-level expansion of short_name."""
    short_tokens = _name_tokens(short_name)
    long_tokens = _name_tokens(long_name)
    if not short_tokens or len(short_tokens) >= len(long_tokens):
        if len(short_name) < 2 or len(short_name) >= len(long_name):
            return False
        return long_name.endswith(short_name)
    size = len(short_tokens)
    return short_tokens == long_tokens[:size] or short_tokens == long_tokens[-size:]


def _is_same_rendered_name_alias(short_name: str, long_name: str, short_translation: str, long_translation: str) -> bool:
    """Return whether two source variants render to the same target name."""
    if not short_translation or short_translation != long_translation:
        return False
    if len(short_name) < 2 or len(short_name) >= len(long_name):
        return False
    return short_name[0] == long_name[0]


def normalize_character_entities(raw_entities: dict) -> dict:
    """Normalize entities and merge conservative short/full-name aliases."""
    if not isinstance(raw_entities, dict):
        return {}

    entities = {
        name: normalize_character_info(info)
        for name, info in raw_entities.items()
        if isinstance(name, str) and name.strip() and isinstance(info, dict)
    }
    names = list(entities)
    alias_to_canonical: dict[str, str] = {}

    for short_name in names:
        short_translation = get_character_translated_name(entities[short_name])
        if not short_translation:
            continue
        candidates = []
        for long_name in names:
            if short_name == long_name:
                continue
            long_translation = get_character_translated_name(entities[long_name])
            if (
                _is_expanded_name(short_name, long_name)
                and _is_expanded_name(short_translation, long_translation)
            ) or _is_same_rendered_name_alias(
                short_name,
                long_name,
                short_translation,
                long_translation,
            ):
                candidates.append(long_name)
        if len(candidates) == 1:
            alias_to_canonical[short_name] = candidates[0]

    for alias, canonical in alias_to_canonical.items():
        if alias not in entities or canonical not in entities:
            continue
        alias_info = entities.pop(alias)
        canonical_info = entities[canonical]
        aliases = canonical_info.setdefault("aliases", [])
        aliases.extend([alias, *alias_info.get("aliases", [])])
        canonical_info["aliases"] = list(dict.fromkeys(aliases))
        if canonical_info.get("role") in ("", "unknown", "minor"):
            alias_role = alias_info.get("role", "")
            if alias_role and alias_role != "unknown":
                canonical_info["role"] = alias_role
        if not canonical_info.get("pronoun"):
            canonical_info["pronoun"] = alias_info.get("pronoun", "")

    return entities


def _build_character_alias_map(entities: dict) -> dict[str, str | None]:
    """Map original and translated character names to canonical original keys."""
    aliases: dict[str, str | None] = {}
    for original, info in entities.items():
        entity_aliases = info.get("aliases", []) if isinstance(info, dict) else []
        for alias in (original, get_character_translated_name(info), *entity_aliases):
            if not alias:
                continue
            if alias in aliases and aliases[alias] != original:
                aliases[alias] = None
            else:
                aliases[alias] = original
    return aliases


def resolve_character_ref(name: str, entities: dict) -> str:
    """Resolve a character reference to its original source key."""
    if name in entities:
        return name
    aliases = _build_character_alias_map(entities)
    resolved = aliases.get(name)
    return resolved or ""


def invert_relationship(relationship: str) -> str:
    """Return the reverse-direction relationship label when known."""
    rel = relationship.strip().lower()
    if rel in SYMMETRIC_RELATIONSHIPS:
        return rel
    return INVERSE_RELATIONSHIPS.get(rel, rel)


def normalize_character_edges(edges: list, entities: dict) -> list[list]:
    """Resolve edge endpoints to original keys, drop unknowns, and deduplicate pairs."""
    normalized: list[list] = []
    seen_pairs: dict[frozenset, int] = {}

    for edge in edges:
        if not isinstance(edge, list) or len(edge) < 3:
            continue
        from_char = resolve_character_ref(edge[0], entities)
        to_char = resolve_character_ref(edge[1], entities)
        if not from_char or not to_char or from_char == to_char:
            continue

        rel_type = str(edge[2]).strip().lower()
        if not rel_type:
            continue

        since = edge[3] if len(edge) > 3 and isinstance(edge[3], int) else None
        pair = frozenset((from_char, to_char))
        new_edge: list[str | int] = [from_char, to_char, rel_type]
        if since is not None:
            new_edge.append(since)

        if pair not in seen_pairs:
            seen_pairs[pair] = len(normalized)
            normalized.append(new_edge)
            continue

        existing = normalized[seen_pairs[pair]]
        if existing[0] == from_char and existing[1] == to_char:
            continue

        inverted = invert_relationship(rel_type)
        if existing[0] == to_char and existing[1] == from_char and existing[2] == inverted:
            continue

    return normalized


def _coerce_chapter(value, fallback: int = 0) -> int:
    """Coerce a chapter marker to a non-negative integer."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return fallback


def normalize_address_rule(rule: dict, entities: dict, chapter: int = 0) -> dict | None:
    """Normalize one direct-address rule to original character keys."""
    if not isinstance(rule, dict):
        return None

    speaker = resolve_character_ref(str(rule.get("speaker", "")).strip(), entities)
    listener = resolve_character_ref(str(rule.get("listener", "")).strip(), entities)
    if not speaker or not listener or speaker == listener:
        return None

    self_ref = rule.get("self", "")
    other_ref = rule.get("other", "")
    notes = rule.get("notes", "")
    self_ref = self_ref.strip() if isinstance(self_ref, str) else ""
    other_ref = other_ref.strip() if isinstance(other_ref, str) else ""
    notes = notes.strip() if isinstance(notes, str) else ""
    if not self_ref and not other_ref and not notes:
        return None

    since = _coerce_chapter(rule.get("since"), fallback=max(0, chapter))
    normalized = {
        "speaker": speaker,
        "listener": listener,
        "self": self_ref,
        "other": other_ref,
        "since": since,
    }

    until = rule.get("until")
    if until is not None:
        until_chapter = _coerce_chapter(until, fallback=-1)
        if until_chapter >= since:
            normalized["until"] = until_chapter

    if notes:
        normalized["notes"] = notes

    return normalized


_TRANSIENT_ADDRESS_PREFIXES = (
    "đồ ",
    "cái đồ ",
    "tên ",
    "thằng ",
    "con nhỏ ",
    "con bé ",
    "đồ chết tiệt",
)

_COMMON_ADDRESS_REFERENCES = {
    "anh",
    "bà",
    "bác",
    "bạn",
    "bệ hạ",
    "bố",
    "cậu",
    "cha",
    "chị",
    "chú",
    "cô",
    "con",
    "dì",
    "em",
    "huynh",
    "mẹ",
    "mày",
    "nàng",
    "ngài",
    "ngươi",
    "ông",
    "sư phụ",
    "ta",
    "tao",
    "thiếp",
    "thầy",
    "tớ",
    "tôi",
}


def _is_transient_address_rule(rule: dict, entities: dict) -> bool:
    """Reject names and obvious one-off insults from persistent address memory."""
    entity_names: list[tuple[str, str]] = []
    for original, info in entities.items():
        if not isinstance(info, dict):
            continue
        entity_names.append((original.casefold(), original))
        translated = get_character_translated_name(info)
        if translated:
            entity_names.append((translated.casefold(), original))
        for alias in info.get("aliases", []):
            if isinstance(alias, str) and alias.strip():
                entity_names.append((alias.strip().casefold(), original))

    other = str(rule.get("other", "")).strip().casefold()
    if other and other not in _COMMON_ADDRESS_REFERENCES:
        has_address_prefix = any(
            other.startswith(f"{reference} ")
            for reference in _COMMON_ADDRESS_REFERENCES
        )
        matched_entities = {
            original
            for name, original in entity_names
            if name and (other == name or _is_expanded_name(other, name))
        }
        if matched_entities and not has_address_prefix:
            return True
    return any(other.startswith(prefix) for prefix in _TRANSIENT_ADDRESS_PREFIXES)


def normalize_address_rules(rules: list, entities: dict, chapter: int = 0) -> list[dict]:
    """Resolve address rules and build one non-overlapping timeline per pair."""
    if not isinstance(rules, list):
        return []

    candidates: list[tuple[int, dict]] = []
    for order, rule in enumerate(rules):
        item = normalize_address_rule(rule, entities, chapter=chapter)
        if not item or _is_transient_address_rule(item, entities):
            continue
        candidates.append((order, item))

    candidates.sort(key=lambda entry: (entry[1].get("since", 0), entry[0]))
    timelines: dict[tuple[str, str], list[dict]] = {}
    for _, item in candidates:
        pair = (item["speaker"], item["listener"])
        timeline = timelines.setdefault(pair, [])
        if not timeline:
            timeline.append(item)
            continue

        previous = timeline[-1]
        same_form = (
            previous.get("self", "") == item.get("self", "")
            and previous.get("other", "") == item.get("other", "")
        )
        continuous = previous.get("until") is None or previous["until"] >= item["since"] - 1
        if same_form and continuous:
            if item.get("notes"):
                previous["notes"] = item["notes"]
            if "until" in item:
                previous["until"] = item["until"]
            continue

        if item["since"] == previous["since"]:
            for field in ("self", "other", "notes"):
                if not item.get(field) and previous.get(field):
                    item[field] = previous[field]
            timeline[-1] = item
            continue

        previous["until"] = min(
            previous.get("until", item["since"] - 1),
            item["since"] - 1,
        )
        timeline.append(item)

    return [rule for timeline in timelines.values() for rule in timeline]


def normalize_glossary_data(data: dict) -> dict:
    """Normalize persisted glossary memory into the current schema."""
    entities = normalize_character_entities(data.get("entities", {}))
    normalized = {
        **data,
        "entities": entities,
        "edges": normalize_character_edges(data.get("edges", []), entities),
        "address_rules": normalize_address_rules(data.get("address_rules", []), entities),
    }
    normalized.pop("pronoun_examples", None)
    return normalized


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
            for key in ("translated_name", "name_vi", "role", "pronoun"):
                if key in info and not isinstance(info[key], str):
                    issues.append(f"entity {original!r}.{key} must be a string")
            aliases = info.get("aliases")
            if aliases is not None and not isinstance(aliases, list):
                issues.append(f"entity {original!r}.aliases must be a list")
            elif isinstance(aliases, list):
                for alias in aliases:
                    if not isinstance(alias, str) or not alias.strip():
                        issues.append(
                            f"entity {original!r}.aliases contains an empty or non-string alias"
                        )

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

    address_rules = data.get("address_rules", [])
    if address_rules is not None and not isinstance(address_rules, list):
        issues.append("address_rules must be a list")
    elif isinstance(address_rules, list):
        entity_names = set(entities) if isinstance(entities, dict) else set()
        for index, rule in enumerate(address_rules):
            if not isinstance(rule, dict):
                issues.append(f"address rule {index} must be an object")
                continue
            speaker = rule.get("speaker")
            listener = rule.get("listener")
            if not isinstance(speaker, str) or not speaker.strip():
                issues.append(f"address rule {index} has an invalid speaker")
            if not isinstance(listener, str) or not listener.strip():
                issues.append(f"address rule {index} has an invalid listener")
            for key in ("self", "other", "notes"):
                if key in rule and not isinstance(rule[key], str):
                    issues.append(f"address rule {index}.{key} must be a string")
            for key in ("since", "until"):
                if key in rule and not isinstance(rule[key], int):
                    issues.append(f"address rule {index}.{key} must be an integer")
            if entity_names:
                if isinstance(speaker, str) and speaker not in entity_names:
                    issues.append(f"address rule {index} references unknown speaker {speaker!r}")
                if isinstance(listener, str) and listener not in entity_names:
                    issues.append(f"address rule {index} references unknown listener {listener!r}")

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
    if CJK_RE.search(name):
        return name in source_text
    escaped = re.escape(name)
    for match in re.finditer(escaped, source_text):
        if _is_name_boundary(source_text, match.start() - 1) and _is_name_boundary(source_text, match.end()):
            return True
    return False


def select_active_glossary_terms(terms: dict[str, str], source_text: str) -> dict[str, str]:
    """Select glossary terms that appear in the current source text."""
    if not terms or not source_text:
        return {}
    return {
        original: translated
        for original, translated in terms.items()
        if isinstance(original, str)
        and isinstance(translated, str)
        and original
        and find_name_in_text(original, source_text)
    }


def select_active_character_context(all_entities: dict, all_edges: list, source_text: str) -> tuple[dict, list]:
    """Select characters and pair relationships that directly appear in the current source text."""
    if not all_entities:
        return {}, []

    normalized = normalize_glossary_data({"entities": all_entities, "edges": all_edges})
    all_entities = normalized["entities"]
    all_edges = normalized["edges"]

    active_names = {
        name
        for name, info in all_entities.items()
        if find_name_in_text(name, source_text)
        or any(find_name_in_text(alias, source_text) for alias in info.get("aliases", []))
    }

    if not active_names:
        return {}, []

    active_edges: list = []
    for edge in all_edges:
        if len(edge) < 3:
            continue
        from_char, to_char = edge[0], edge[1]
        if from_char in active_names and to_char in active_names:
            active_edges.append(edge)

    active_entities = {
        name: all_entities[name]
        for name in active_names
        if name in all_entities
    }

    return active_entities, active_edges


def select_active_address_rules(address_rules: list, active_entities: dict, current_chapter: int = 0) -> list[dict]:
    """Select direct-address rules for active characters and the current chapter."""
    if not address_rules or not active_entities:
        return []

    active_names = set(active_entities)
    selected_by_pair: dict[tuple[str, str], dict] = {}
    for rule in address_rules:
        if rule.get("speaker") not in active_names or rule.get("listener") not in active_names:
            continue
        if current_chapter > 0:
            since = rule.get("since", 0)
            until = rule.get("until")
            if isinstance(since, int) and since > current_chapter:
                continue
            if isinstance(until, int) and until < current_chapter:
                continue
        pair = (rule["speaker"], rule["listener"])
        existing = selected_by_pair.get(pair)
        if not existing or rule.get("since", 0) >= existing.get("since", 0):
            selected_by_pair[pair] = rule
    return list(selected_by_pair.values())


def merge_character_context(
    data: dict,
    entities: dict,
    edges: list,
    address_rules: list | None = None,
    chapter: int = 0,
) -> dict:
    """Merge character entities and relationship edges into glossary data."""
    data = normalize_glossary_data(data)
    existing_entities: dict = data.get("entities", {})
    for name, info in entities.items():
        translated_name = get_character_translated_name(info)
        if name not in existing_entities:
            existing_entities[name] = {
                "translated_name": translated_name,
                "role": info.get("role", "unknown"),
                "pronoun": info.get("pronoun", ""),
            }
        else:
            if translated_name:
                existing_entities[name]["translated_name"] = translated_name
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

    existing_entities = normalize_character_entities(existing_entities)
    existing_edges = normalize_character_edges(data.get("edges", []) + tagged_edges, existing_entities)
    existing_address_rules = normalize_address_rules(
        data.get("address_rules", []) + (address_rules or []),
        existing_entities,
        chapter=chapter,
    )

    return {
        **data,
        "entities": existing_entities,
        "edges": existing_edges,
        "address_rules": existing_address_rules,
    }


def upsert_relationship(
    data: dict,
    from_char: str,
    to_char: str,
    relationship: str,
    since_chapter: int | None = None,
) -> dict:
    """Add or update one relationship edge, preserving the one-edge-per-pair rule."""
    data = normalize_glossary_data(data)
    entities = data.get("entities", {})
    from_char = resolve_character_ref(from_char, entities) or from_char
    to_char = resolve_character_ref(to_char, entities) or to_char
    relationship = relationship.strip().lower()
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

    edge: list[str | int] = [from_char, to_char, relationship]
    if since_chapter is not None:
        edge.append(since_chapter)
    edges.append(edge)
    return {**data, "edges": edges}


def format_relationships_shorthand(entities: dict, edges: list) -> str:
    """Format active character context as compact shorthand for LLM prompts."""
    if not entities:
        return ""

    notable_roles = {"protagonist", "antagonist", "supporting"}
    name_parts = []
    roles_parts = []
    for name, info in entities.items():
        translated_name = get_character_translated_name(info)
        if translated_name and translated_name != name:
            name_parts.append(f"{name}={translated_name}")
        role = info.get("role", "")
        pronoun = info.get("pronoun", "")
        if role in notable_roles or pronoun:
            tag = role
            if pronoun:
                tag += f', pronoun="{pronoun}"'
            roles_parts.append(f"{name}[{tag}]")
        elif role:
            roles_parts.append(f"{name}[{role}]")

    rel_parts = []
    for edge in edges:
        if len(edge) < 3:
            continue
        from_char, to_char, rel_type = edge[0], edge[1], edge[2]
        rel_parts.append(f"{from_char}({rel_type})->{to_char}")

    lines = ["=== CHARACTERS ==="]
    if name_parts:
        lines.append("Names: " + ", ".join(name_parts))
    if roles_parts:
        lines.append("Roles: " + ", ".join(roles_parts))
    if rel_parts:
        lines.append("Relations: " + "; ".join(rel_parts))
    lines.append("=== END CHARACTERS ===")

    return "\n".join(lines)


def format_address_rules(entities: dict, address_rules: list, target_language: str = "vi") -> str:
    """Format active direct-address rules for translator prompts."""
    if not entities or not address_rules:
        return ""

    lines = ["=== ADDRESS RULES ==="]
    for rule in address_rules:
        speaker = rule.get("speaker", "")
        listener = rule.get("listener", "")

        parts = []
        if rule.get("self"):
            parts.append(f'self="{rule["self"]}"')
        if rule.get("other"):
            parts.append(f'other="{rule["other"]}"')

        lines.append(f"{speaker} -> {listener}: " + ", ".join(parts))
    lines.append("=== END ADDRESS RULES ===")
    return "\n".join(lines)
