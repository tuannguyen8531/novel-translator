"""
Chunker Node — Split source text into translatable chunks.
"""

from src.models.state import TranslationState
from src.config import config
from src.utils.text import split_into_chunks


def chunker_node(state: TranslationState) -> dict:
    """Split source text into chunks for translation."""
    chunks = split_into_chunks(
        state["source_text"],
        chunk_size=config.chunk_size,
        overlap=config.chunk_overlap,
    )

    print(f"  📦 Split into {len(chunks)} chunks (avg {sum(len(c) for c in chunks) // max(len(chunks), 1)} chars)")

    return {
        "chunks": chunks,
        "current_chunk_index": 0,
        "translated_chunks": [],
        "retry_count": 0,
    }
