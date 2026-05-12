"""
Chunker Node — Split source text into translatable chunks.
"""

from src.models.state import TranslationState
from src.config import config
from src.domain.chunking import split_into_chunks


def chunker_node(state: TranslationState) -> dict:
    """Split source text into chunks for translation."""
    chunks = split_into_chunks(
        state["source_text"],
        chunk_size=config.chunk_size,
        overlap=config.chunk_overlap,
    )

    return {
        "chunks": chunks,
        "current_chunk_index": 0,
        "translated_chunks": [],
        "retry_count": 0,
    }
