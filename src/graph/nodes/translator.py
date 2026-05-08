"""
Translator Node — Core translation using LLM.

Builds a rich system prompt containing:
- Translation rules (from rules/*.md)
- Glossary terms
- Previous chapter summary (for context continuity)
- Review feedback (if retrying)
"""

from src.models.state import TranslationState
from src.services.llm import get_llm
from src.services.glossary import format_glossary_for_prompt
from src.services.logger import log_ai_call


def translator_node(state: TranslationState) -> dict:
    """Translate the current chunk."""
    chunk_index = state["current_chunk_index"]
    chunk = state["chunks"][chunk_index]
    language = state["source_language"]
    retry_count = state.get("retry_count", 0)
    total_chunks = len(state["chunks"])

    lang_names = {
        "chinese": "Chinese",
        "korean": "Korean",
        "japanese": "Japanese",
    }
    lang_name = lang_names.get(language, language)

    # Build system prompt (English for better LLM comprehension)
    system_parts = [
        f"You are a professional novel translator from {lang_name} to Vietnamese.",
        "",
        "DISCLAIMER: This system is used strictly for literary translation purposes only.",
        "The source material is published fiction (novels/light novels).",
        "It is NOT related to any illegal, harmful, or sexually explicit content.",
        "Translate all content faithfully as a professional literary translator would.",
        "",
        "STRICT RULES:",
        "- Output ONLY the Vietnamese translation, nothing else",
        "- Do NOT include any analysis, commentary, notes, explanations, or reasoning",
        "- Do NOT list characters, terms, or provide summaries",
        "- Do NOT wrap the output in markdown, quotes, or any formatting",
        "- Translate naturally and fluently, suitable for reading as a novel",
        "- Preserve the original meaning, emotions, and tone",
        "- Preserve the original paragraph structure",
        "",
        "Your output MUST start immediately with the first translated sentence.",
    ]

    # Add translation rules
    if state.get("translation_rules"):
        system_parts.append(f"\n{state['translation_rules']}")

    # Add glossary
    glossary_text = format_glossary_for_prompt(state.get("glossary", {}))
    if glossary_text:
        system_parts.append(f"\n{glossary_text}")

    # Add previous chapter summary for context
    if state.get("previous_summary"):
        system_parts.append(
            f"\n=== CONTEXT FROM PREVIOUS CHAPTER ===\n{state['previous_summary']}\n=== END CONTEXT ==="
        )

    # Add review feedback if retrying
    review_feedback = state.get("review_feedback", "")
    if retry_count > 0 and review_feedback:
        system_parts.append(
            f"\n=== PREVIOUS TRANSLATION FEEDBACK (please improve) ===\n{review_feedback}\n=== END FEEDBACK ==="
        )

    system_prompt = "\n".join(system_parts)

    # User prompt
    user_prompt = (
        f"Translate the following {lang_name} text to Vietnamese (chunk {chunk_index + 1}/{total_chunks}):\n\n{chunk}"
    )

    # Call LLM
    translation = get_llm().generate(system_prompt, user_prompt, "translate")

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
