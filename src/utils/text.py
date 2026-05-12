"""
Text processing utilities.
"""

import re
import unicodedata


def detect_language_heuristic(text: str) -> str:
    """
    Detect language based on Unicode character ranges.
    Returns: "chinese" | "korean" | "japanese" | "unknown"

    Heuristic:
    - Korean: Hangul block (U+AC00-U+D7AF, U+1100-U+11FF)
    - Japanese: Hiragana (U+3040-U+309F) or Katakana (U+30A0-U+30FF)
    - Chinese: CJK Unified Ideographs (U+4E00-U+9FFF) without Japanese kana
    """
    hangul_count = 0
    kana_count = 0
    cjk_count = 0
    total_meaningful = 0

    for char in text:
        if char.isspace() or unicodedata.category(char).startswith("P"):
            continue
        total_meaningful += 1
        cp = ord(char)

        if (0xAC00 <= cp <= 0xD7AF) or (0x1100 <= cp <= 0x11FF) or (0x3130 <= cp <= 0x318F):
            hangul_count += 1
        elif (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF):
            kana_count += 1
        elif 0x4E00 <= cp <= 0x9FFF:
            cjk_count += 1

    if total_meaningful == 0:
        return "unknown"

    hangul_ratio = hangul_count / total_meaningful
    kana_ratio = kana_count / total_meaningful
    cjk_ratio = cjk_count / total_meaningful

    if hangul_ratio > 0.15:
        return "korean"
    if kana_ratio > 0.05:
        return "japanese"
    if cjk_ratio > 0.3:
        return "chinese"

    return "unknown"


def split_into_chunks(text: str, chunk_size: int = 1500, overlap: int = 100) -> list[str]:
    """
    Split text into chunks for translation.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. Group paragraphs into chunks of ~chunk_size characters
    3. Add overlap between chunks for context continuity
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        # Fallback: split by single newlines
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return [text] if text.strip() else []

    chunks = []
    current_chunk_parts = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        # If single paragraph exceeds chunk_size, split by sentences
        if para_size > chunk_size:
            # Flush current chunk first
            if current_chunk_parts:
                chunks.append("\n\n".join(current_chunk_parts))
                current_chunk_parts = []
                current_size = 0

            # Split long paragraph by sentence boundaries
            sentences = _split_sentences(para)
            for sent in sentences:
                if current_size + len(sent) > chunk_size and current_chunk_parts:
                    chunks.append("\n\n".join(current_chunk_parts))
                    # Keep overlap from end of previous chunk
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

        # Check if adding this paragraph exceeds chunk_size
        if current_size + para_size > chunk_size and current_chunk_parts:
            chunks.append("\n\n".join(current_chunk_parts))
            # Overlap: keep last part of previous chunk
            if overlap > 0 and current_chunk_parts:
                last_part = current_chunk_parts[-1]
                overlap_text = last_part[-overlap:] if len(last_part) > overlap else last_part
                current_chunk_parts = [overlap_text]
                current_size = len(overlap_text)
            else:
                current_chunk_parts = []
                current_size = 0

        current_chunk_parts.append(para)
        current_size += para_size

    # Don't forget the last chunk
    if current_chunk_parts:
        chunks.append("\n\n".join(current_chunk_parts))

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling CJK and Western punctuation."""
    # CJK sentence endings: 。！？
    # Western: . ! ?
    # Split but keep the punctuation with the sentence
    pattern = r'(?<=[。！？.!?\n])\s*'
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]
