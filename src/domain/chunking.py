"""Chunking rules for long-form translation."""

import re

from src.domain.illustrations import parse_illustration_marker


def split_into_chunks(text: str, chunk_size: int = 1500, overlap: int = 100) -> list[str]:
    """
    Split text into chunks for translation.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. Group paragraphs into chunks of ~chunk_size characters
    3. Add overlap between chunks for context continuity
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return [text] if text.strip() else []

    chunks = []
    current_chunk_parts = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        if para_size > chunk_size and not parse_illustration_marker(para):
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_size = 0

            sentences = split_sentences(para)
            for sent in sentences:
                if current_size + len(sent) > chunk_size and current_chunk_parts:
                    chunks.append("\n\n".join(current_chunk_parts))
                    if overlap > 0 and current_chunk_parts:
                        overlap_text = current_chunk_parts[-1][-overlap:]
                        current_chunk_parts = [overlap_text]
                        current_size = len(overlap_text)
                    else:
                        current_chunk_parts = []
                        current_size = 0
                current_chunk_parts.append(sent)
                current_size += len(sent)
            continue

        if current_size + para_size > chunk_size and current_chunk_parts:
            chunks.append("\n\n".join(current_chunk_parts))
            if overlap > 0 and current_chunk_parts:
                last_part = current_chunk_parts[-1]
                if parse_illustration_marker(last_part):
                    current_chunk_parts = []
                    current_size = 0
                else:
                    overlap_text = last_part[-overlap:] if len(last_part) > overlap else last_part
                    current_chunk_parts = [overlap_text]
                    current_size = len(overlap_text)
            else:
                current_chunk_parts = []
                current_size = 0

        current_chunk_parts.append(para)
        current_size += para_size

    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return chunks


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling CJK and Western punctuation."""
    pattern = r"(?<=[。！？.!?\n])\s*"
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]
