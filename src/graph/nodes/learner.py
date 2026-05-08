"""
Learner Node — Extract glossary terms and create chapter summary.

Runs after all chunks are translated. Responsible for:
1. Extracting new terms (character names, place names, special terms)
2. Creating a chapter summary for cross-chapter context
3. Saving both to the glossary JSON file
"""

import json
import re

from src.models.state import TranslationState
from src.services.llm import get_llm
from src.services.glossary import save_glossary, save_chapter_summary, save_source_language, save_characters_batch
from src.services.logger import log_ai_call, log_error
from src.config import config

# Minimum occurrences in text for a term to qualify for glossary
MIN_TERM_FREQUENCY = 3


def _count_occurrences(text: str, term: str) -> int:
    """Count case-insensitive occurrences of term in text."""
    if not term or len(term) < 2:
        return 0
    # Escape regex special chars in term
    escaped = re.escape(term)
    return len(re.findall(escaped, text, re.IGNORECASE))


def _filter_by_frequency(text: str, terms: dict[str, str], min_count: int) -> dict[str, str]:
    """Keep only terms that appear at least min_count times in the text."""
    filtered = {}
    for original, translation in terms.items():
        count = _count_occurrences(text, original)
        if count >= min_count:
            filtered[original] = translation
    return filtered


def learner_node(state: TranslationState) -> dict:
    """Extract terms and create summary from the translated chapter."""
    novel_name = state["novel_name"]
    chapter_number = state["chapter_number"]
    language = state["source_language"]

    # Combine all translated chunks
    full_translation = "\n\n".join(state["translated_chunks"])
    # Also need source for term extraction
    source_text = state["source_text"]

    # --- 1. Extract terms + character relationships (single call) ---
    existing_glossary = state.get("glossary", {})
    existing_terms_str = "\n".join(f"  {k} → {v}" for k, v in existing_glossary.items()) if existing_glossary else "(none)"

    existing_characters = state.get("characters", {})
    existing_entities = existing_characters.get("entities", {})
    existing_edges = existing_characters.get("edges", [])
    existing_chars_str = "(none)"
    if existing_entities:
        entity_parts = []
        for name_orig, info in existing_entities.items():
            name_vi = info.get("name_vi", "")
            role = info.get("role", "")
            pronoun = info.get("pronoun", "")
            pronoun_str = f' pronoun="{pronoun}"' if pronoun else ""
            entity_parts.append(f"  {name_orig}" + (f" ({name_vi})" if name_vi else "") + (f" [{role}{pronoun_str}]" if role or pronoun else ""))
        if existing_edges:
            edge_parts = []
            for edge in existing_edges:
                if len(edge) >= 3:
                    from_vi = existing_entities.get(edge[0], {}).get("name_vi", edge[0])
                    to_vi = existing_entities.get(edge[1], {}).get("name_vi", edge[1])
                    edge_parts.append(f"  {from_vi}({edge[2]})->{to_vi}")
            existing_chars_str = "Entities:\n" + "\n".join(entity_parts) + "\nRelations:\n" + "\n".join(edge_parts)
        else:
            existing_chars_str = "Entities:\n" + "\n".join(entity_parts)

    learn_system_prompt = f"""You are analyzing a novel chapter. Extract important terms AND character relationships.

=== TERMS ===
STRICT CRITERIA — only include terms that meet ALL of these:
1. Character names (people, beings with names)
2. Place names (locations, realms, organizations with names)
3. Special recurring terms (unique skills, cultivation levels, world-specific concepts that will appear repeatedly)

EXCLUDE:
- Common words, verbs, adjectives, descriptive phrases
- One-off terms that appear only once or twice
- Generic terms like "sword", "fire", "mountain" unless they are proper names
- Translated dialogue fragments or idioms
- Terms already in the existing glossary

Existing terms (DO NOT repeat):
{existing_terms_str}

=== CHARACTERS ===
Identify characters that appear in this chapter and their relationships to each other.

EXISTING CHARACTERS (update relationships if new ones are discovered):
{existing_chars_str}

RULES:
- Only include characters that actually appear or are mentioned in this chapter
- Relationship types should be specific: mother, father, sibling, friend, enemy, master,
  disciple, rival, classmate, teacher, romantic interest, crush, etc.
- Avoid vague relationships like "knows" or "met"
- Store each relationship ONCE — do NOT add both A→B and B→A for the same pair
  (e.g. if you add [A, B, "mother"], do NOT also add [B, A, "son"])
- If a character's role is unclear, use "minor"
- Assign a consistent Vietnamese pronoun for each character based on age, gender, status,
  and relationship dynamics. Examples: "cậu", "anh ấy", "ông", "bà", "cô ấy", "chị ấy",
  "hắn", "y", "nó", "ta", "quý ngài", "tiểu thư". Use the SAME pronoun across all chapters.

Respond with JSON ONLY (no other text):
{{
    "terms": {{
        "original term": "Vietnamese translation"
    }},
    "characters": {{
        "entities": {{
            "original name": {{
                "name_vi": "Vietnamese name",
                "role": "protagonist | antagonist | supporting | minor",
                "pronoun": "Vietnamese pronoun (e.g. cậu, anh ấy, cô ấy, hắn)"
            }}
        }},
        "edges": [
            ["from_original_name", "to_original_name", "relationship_type"]
        ]
    }}
}}"""

    learn_user_prompt = f"""=== SOURCE TEXT ({language}) ===
{source_text[:4000]}

=== VIETNAMESE TRANSLATION ===
{full_translation[:4000]}"""

    new_terms = {}
    new_characters = {}
    learn_response = ""
    try:
        learn_response = get_llm().generate(learn_system_prompt, learn_user_prompt, "learn")

        json_start = learn_response.find("{")
        json_end = learn_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            learn_data = json.loads(learn_response[json_start:json_end])
        else:
            learn_data = json.loads(learn_response)
        new_terms = learn_data.get("terms", {})
        new_characters = learn_data.get("characters", {})
    except Exception as e:
        log_error("Failed to extract terms and characters", e, chapter=chapter_number)
        print(f"\n  [Warning] Failed to extract terms and characters: {e}")

    # Filter: only keep terms that appear at least MIN_TERM_FREQUENCY times
    if new_terms:
        new_terms = _filter_by_frequency(source_text, new_terms, MIN_TERM_FREQUENCY)

    if new_terms:
        save_glossary(novel_name, new_terms)

    new_entities = new_characters.get("entities", {})
    new_edges = new_characters.get("edges", [])

    if new_entities or new_edges:
        save_characters_batch(novel_name, new_entities, new_edges, chapter=chapter_number)
        print(f"  📝 Updated {len(new_entities)} character(s), {len(new_edges)} relationship(s)")

    save_source_language(novel_name, state["source_language"])

    log_ai_call(
        "learn",
        system_prompt=learn_system_prompt,
        user_prompt=learn_user_prompt,
        response=learn_response,
        chapter=chapter_number,
        new_terms_count=len(new_terms),
        terms=new_terms,
        characters_count=len(new_characters),
    )

    # --- 3. Create chapter summary ---
    if not config.enable_summary:
        summary_response = ""
    else:
        summary_system_prompt = """Write a very concise summary of this chapter in 2-3 sentences (max 50 words).
Include ONLY: key events, main characters involved, and any important plot developments.
Write in Vietnamese. Output ONLY the summary, nothing else."""

        summary_user_prompt = f"Summarize chapter {chapter_number}:\n\n{full_translation[:4000]}"

        try:
            summary_response = get_llm().generate(summary_system_prompt, summary_user_prompt, "learn_summary")

            save_chapter_summary(novel_name, chapter_number, summary_response)

            log_ai_call(
                "learn_summary",
                system_prompt=summary_system_prompt,
                user_prompt=summary_user_prompt,
                response=summary_response,
                chapter=chapter_number,
                summary_length=len(summary_response),
            )
        except Exception as e:
            log_error("Failed to generate summary", e, chapter=chapter_number)
            print(f"\n  [Warning] Failed to generate summary: {e}")
            summary_response = ""

    return {
        "new_terms": new_terms,
        "new_characters": new_characters,
        "chapter_summary": summary_response,
        "final_translation": full_translation,
    }
