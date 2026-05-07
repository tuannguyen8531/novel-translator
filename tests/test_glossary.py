"""Tests for glossary service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.services.glossary import (
    load_glossary,
    save_glossary,
    load_chapter_summary,
    save_chapter_summary,
    load_chapter_summaries_recent,
    format_glossary_for_prompt,
    load_source_language,
    save_source_language,
    load_translated_chapters,
    mark_chapter_translated,
    GLOSSARY_DIR,
)


class TestGlossary:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch("src.services.glossary.GLOSSARY_DIR", Path(self.temp_dir.name))
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_save_and_load_glossary(self):
        save_glossary("test-novel", {"李白": "Lý Bạch"})
        result = load_glossary("test-novel")
        assert result == {"李白": "Lý Bạch"}

    def test_merge_glossary(self):
        save_glossary("test-novel", {"李白": "Lý Bạch"})
        save_glossary("test-novel", {"杜甫": "Đỗ Phủ"})
        result = load_glossary("test-novel")
        assert result == {"李白": "Lý Bạch", "杜甫": "Đỗ Phủ"}

    def test_merge_overrides_existing(self):
        save_glossary("test-novel", {"李白": "Lý Bạch"})
        save_glossary("test-novel", {"李白": "Lý Bạch Mới"})
        result = load_glossary("test-novel")
        assert result["李白"] == "Lý Bạch Mới"

    def test_load_nonexistent(self):
        result = load_glossary("nonexistent")
        assert result == {}

    def test_save_and_load_chapter_summary(self):
        save_chapter_summary("test-novel", 1, "Chapter 1 summary")
        result = load_chapter_summary("test-novel", 1)
        assert result == "Chapter 1 summary"

    def test_load_nonexistent_summary(self):
        result = load_chapter_summary("nonexistent", 1)
        assert result == ""

    def test_load_recent_summaries(self):
        for i in range(1, 6):
            save_chapter_summary("test-novel", i, f"Summary {i}")

        result = load_chapter_summaries_recent("test-novel", 6, max_count=3)
        assert "Chapter 3" in result
        assert "Chapter 4" in result
        assert "Chapter 5" in result
        assert "Chapter 2" not in result

    def test_recent_summaries_order(self):
        save_chapter_summary("test-novel", 1, "First")
        save_chapter_summary("test-novel", 2, "Second")
        save_chapter_summary("test-novel", 3, "Third")

        result = load_chapter_summaries_recent("test-novel", 4, max_count=3)
        first_idx = result.index("Chapter 1")
        second_idx = result.index("Chapter 2")
        third_idx = result.index("Chapter 3")
        assert first_idx < second_idx < third_idx

    def test_format_glossary_for_prompt(self):
        terms = {"李白": "Lý Bạch", "杜甫": "Đỗ Phủ"}
        result = format_glossary_for_prompt(terms)
        assert "GLOSSARY" in result
        assert "李白 → Lý Bạch" in result
        assert "杜甫 → Đỗ Phủ" in result
        assert "END GLOSSARY" in result

    def test_format_empty_glossary(self):
        assert format_glossary_for_prompt({}) == ""

    def test_save_and_load_source_language(self):
        save_source_language("test-novel", "chinese")
        result = load_source_language("test-novel")
        assert result == "chinese"

    def test_load_source_language_nonexistent(self):
        result = load_source_language("nonexistent")
        assert result == ""

    def test_save_empty_language_skips(self):
        save_source_language("test-novel", "")
        result = load_source_language("test-novel")
        assert result == ""

    def test_mark_and_load_translated_chapters(self):
        mark_chapter_translated("test-novel", 1)
        mark_chapter_translated("test-novel", 3)
        result = load_translated_chapters("test-novel")
        assert result == {1, 3}

    def test_translated_chapters_sorted(self):
        mark_chapter_translated("test-novel", 5)
        mark_chapter_translated("test-novel", 1)
        mark_chapter_translated("test-novel", 3)
        result = load_translated_chapters("test-novel")
        assert result == {1, 3, 5}

    def test_translated_chapters_no_duplicates(self):
        mark_chapter_translated("test-novel", 1)
        mark_chapter_translated("test-novel", 1)
        result = load_translated_chapters("test-novel")
        assert result == {1}

    def test_load_translated_chapters_nonexistent(self):
        result = load_translated_chapters("nonexistent")
        assert result == set()
