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
from src.services.glossary import save_glossary, save_chapter_summary, save_source_language
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

    # --- 1. Extract new glossary terms ---
    existing_glossary = state.get("glossary", {})
    existing_terms_str = "\n".join(f"  {k} → {v}" for k, v in existing_glossary.items()) if existing_glossary else "(none)"

    term_system_prompt = f"""You are a linguistic analysis expert. Extract important terms from the novel passage below.

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

Respond with JSON ONLY (no other text):
{{
    "terms": {{
        "original term": "Vietnamese translation",
        ...
    }}
}}"""

    term_user_prompt = f"""=== SOURCE TEXT ({language}) ===
{source_text[:3000]}

=== VIETNAMESE TRANSLATION ===
{full_translation[:3000]}"""

    new_terms = {}
    term_response = ""
    try:
        term_response = get_llm().generate(term_system_prompt, term_user_prompt, "learn_terms")

        json_start = term_response.find("{")
        json_end = term_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            term_data = json.loads(term_response[json_start:json_end])
        else:
            term_data = json.loads(term_response)
        new_terms = term_data.get("terms", {})
    except Exception as e:
        log_error("Failed to extract terms", e, chapter=chapter_number)
        print(f"\n  [Warning] Failed to extract terms: {e}")

    # Filter: only keep terms that appear at least MIN_TERM_FREQUENCY times
    if new_terms:
        new_terms = _filter_by_frequency(source_text, new_terms, MIN_TERM_FREQUENCY)

    if new_terms:
        save_glossary(novel_name, new_terms)

    # Save detected source language for future chapters
    save_source_language(novel_name, state["source_language"])

    log_ai_call(
        "learn_terms",
        system_prompt=term_system_prompt,
        user_prompt=term_user_prompt,
        response=term_response,
        chapter=chapter_number,
        new_terms_count=len(new_terms),
        terms=new_terms,
    )

    # --- 2. Create chapter summary ---
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
        "chapter_summary": summary_response,
        "final_translation": full_translation,
    }
