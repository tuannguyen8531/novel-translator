"""
Learner Node — Extract glossary terms and create chapter summary.

Runs after all chunks are translated. Responsible for:
1. Extracting new terms (character names, place names, special terms)
2. Creating a chapter summary for cross-chapter context
3. Saving both to the glossary JSON file
"""

import json

from src.models.state import TranslationState
from src.services.llm import llm
from src.services.glossary import save_glossary, save_chapter_summary
from src.services.logger import log_ai_call


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

Extract:
- Character names (original → Vietnamese translation)
- Place names (original → Vietnamese translation)
- Special terms (skills, items, organizations, etc.)
- Recurring important phrases

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

    term_response = llm.generate(term_system_prompt, term_user_prompt)

    new_terms = {}
    try:
        json_start = term_response.find("{")
        json_end = term_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            term_data = json.loads(term_response[json_start:json_end])
        else:
            term_data = json.loads(term_response)
        new_terms = term_data.get("terms", {})
    except (json.JSONDecodeError, ValueError):
        pass  # Failed to extract terms, continue without

    if new_terms:
        save_glossary(novel_name, new_terms)
        print(f"  📚 Extracted {len(new_terms)} new terms → glossary/{novel_name}.json")

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
    summary_system_prompt = """Write a very concise summary of this chapter in 2-3 sentences (max 50 words).
Include ONLY: key events, main characters involved, and any important plot developments.
Write in Vietnamese. Output ONLY the summary, nothing else."""

    summary_user_prompt = f"Summarize chapter {chapter_number}:\n\n{full_translation[:4000]}"

    summary_response = llm.generate(summary_system_prompt, summary_user_prompt)

    save_chapter_summary(novel_name, chapter_number, summary_response)
    print(f"  📋 Chapter {chapter_number} summary saved ({len(summary_response)} chars)")

    log_ai_call(
        "learn_summary",
        system_prompt=summary_system_prompt,
        user_prompt=summary_user_prompt,
        response=summary_response,
        chapter=chapter_number,
        summary_length=len(summary_response),
    )

    return {
        "new_terms": new_terms,
        "chapter_summary": summary_response,
        "final_translation": full_translation,
    }
