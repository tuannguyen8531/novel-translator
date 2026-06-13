"""
Translator Node — Core translation using LLM.

Builds a system prompt from template with:
- Translation rules (from rules/*.md)
- Glossary terms
- Previous chapter summary (for context continuity)
- Character relationships and direct-address rules
- Review feedback (if retrying)
"""

from src.models.state import TranslationState
from src.services.llm import get_llm
from src.domain.glossary import format_address_rules, format_glossary_for_prompt, format_relationships_shorthand
from src.domain.illustrations import detach_illustration_markers, restore_illustration_markers
from src.services.logger import log_ai_call
from src.prompts import render_prompt
from src.domain.target_language import target_language_name


def translator_node(state: TranslationState) -> dict:
    """Translate the current chunk."""
    chunk_index = state["current_chunk_index"]
    chunk = state["chunks"][chunk_index]
    language = state["source_language"]
    target_language = state.get("target_language", "vi")
    target_name = target_language_name(target_language)
    retry_count = state.get("retry_count", 0)
    total_chunks = len(state["chunks"])
    translatable_chunk, illustration_placements = detach_illustration_markers(chunk)

    lang_names = {
        "chinese": "Chinese",
        "korean": "Korean",
        "japanese": "Japanese",
    }
    lang_name = lang_names.get(language, language)

    # Build optional sections
    rules = state.get("translation_rules", "")
    translation_rules = f"\n{rules}" if rules else ""

    glossary_text = format_glossary_for_prompt(state.get("glossary", {}))
    glossary = f"\n{glossary_text}" if glossary_text else ""

    char_data = state.get("characters", {})
    entities = char_data.get("entities", {})
    edges = char_data.get("edges", [])
    address_rules = char_data.get("address_rules", [])
    relationships_text = format_relationships_shorthand(entities, edges)
    characters = f"\n{relationships_text}" if relationships_text else ""
    address_rules_text = format_address_rules(entities, address_rules, target_language=target_language)
    address_rules_prompt = f"\n{address_rules_text}" if address_rules_text else ""

    previous_summary = state.get("previous_summary", "")
    if previous_summary:
        previous_summary = f"\n=== CONTEXT FROM PREVIOUS CHAPTER ===\n{previous_summary}\n=== END CONTEXT ==="

    review_feedback = ""
    if retry_count > 0 and state.get("review_feedback"):
        review_feedback = f"\n=== PREVIOUS TRANSLATION FEEDBACK (please improve) ===\n{state['review_feedback']}\n=== END FEEDBACK ==="

    system_prompt = render_prompt(
        "translator_system",
        target_language=target_language,
        lang_name=lang_name,
        target_name=target_name,
        translation_rules=translation_rules,
        glossary=glossary,
        characters=characters,
        address_rules=address_rules_prompt,
        previous_summary=previous_summary,
        review_feedback=review_feedback,
    )

    user_prompt = (
        f"Translate the following {lang_name} text to {target_name} (chunk {chunk_index + 1}/{total_chunks}):\n\n{translatable_chunk}"
    )

    if translatable_chunk:
        translation = get_llm().generate(system_prompt, user_prompt, "translate")
    else:
        translation = ""
    translation = restore_illustration_markers(translation, illustration_placements)

    log_ai_call(
        "translate",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=translation,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        chunk_length=len(chunk),
        translation_length=len(translation),
        retry_count=retry_count,
    )

    return {"current_translation": translation}
