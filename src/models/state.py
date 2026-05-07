"""
LangGraph State definition for the Novel Translation Pipeline.

The State flows through every node in the graph:
  detect → chunk → context → [translate → review]* → learn → save
"""

from typing import TypedDict


class TranslationState(TypedDict):
    """Central state object for the translation pipeline."""

    # --- Input (set at invocation) ---
    source_text: str                    # Full raw text to translate
    source_language: str                # "chinese" | "korean" | "japanese" | "" (auto-detect)
    novel_name: str                     # For glossary lookup
    chapter_number: int                 # Current chapter number

    # --- Context (loaded by context node) ---
    translation_rules: str              # Rules from rules/{language}.md
    glossary: dict[str, str]            # Term → Translation mapping
    previous_summary: str               # Summary of previous chapter

    # --- Chunk Processing ---
    chunks: list[str]                   # Text split into translatable chunks
    current_chunk_index: int            # Which chunk we're translating (0-based)
    translated_chunks: list[str]        # Completed translations (parallel to chunks)
    current_translation: str            # Working translation for current chunk

    # --- Review Loop ---
    review_score: float                 # Quality score (0.0 - 1.0)
    review_feedback: str                # What to improve
    retry_count: int                    # Current retry count for this chunk

    # --- Learning Output ---
    new_terms: dict[str, str]           # New glossary terms extracted
    chapter_summary: str                # Summary for next chapter context

    # --- Final Output ---
    final_translation: str              # Complete translated text


def initial_state(
    source_text: str,
    source_language: str,
    novel_name: str,
    chapter_number: int,
) -> TranslationState:
    """Create a properly initialized TranslationState."""
    return TranslationState(
        source_text=source_text,
        source_language=source_language,
        novel_name=novel_name,
        chapter_number=chapter_number,
        translation_rules="",
        glossary={},
        previous_summary="",
        chunks=[],
        current_chunk_index=0,
        translated_chunks=[],
        current_translation="",
        review_score=0.0,
        review_feedback="",
        retry_count=0,
        new_terms={},
        chapter_summary="",
        final_translation="",
    )
