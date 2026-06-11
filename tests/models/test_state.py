"""Tests for TranslationState and initial_state factory."""

import pytest
from src.models.state import TranslationState, initial_state


class TestInitialState:
    def test_all_fields_present(self):
        state = initial_state(
            source_text="test",
            source_language="chinese",
            novel_name="test-novel",
            chapter_number=1,
        )

        required_fields = [
            "source_text", "source_language", "target_language", "novel_name", "chapter_number",
            "translation_rules", "glossary", "previous_summary",
            "chunks", "current_chunk_index", "translated_chunks",
            "current_translation", "review_score", "review_feedback",
            "retry_count", "post_check_issues", "quality_reports",
            "new_terms", "chapter_summary", "final_translation",
        ]
        for field in required_fields:
            assert field in state

    def test_input_fields_set(self):
        state = initial_state(
            source_text="hello world",
            source_language="korean",
            novel_name="my-novel",
            chapter_number=5,
        )
        assert state["source_text"] == "hello world"
        assert state["source_language"] == "korean"
        assert state["target_language"] == "vi"
        assert state["novel_name"] == "my-novel"
        assert state["chapter_number"] == 5

    def test_defaults(self):
        state = initial_state(
            source_text="test",
            source_language="",
            novel_name="test",
            chapter_number=1,
        )
        assert state["translation_rules"] == ""
        assert state["target_language"] == "vi"
        assert state["glossary"] == {}
        assert state["previous_summary"] == ""
        assert state["chunks"] == []
        assert state["current_chunk_index"] == 0
        assert state["translated_chunks"] == []
        assert state["current_translation"] == ""
        assert state["review_score"] == 0.0
        assert state["review_feedback"] == ""
        assert state["retry_count"] == 0
        assert state["post_check_issues"] == []
        assert state["quality_reports"] == []
        assert state["new_terms"] == {}
        assert state["chapter_summary"] == ""
        assert state["final_translation"] == ""

    def test_is_typed_dict(self):
        state = initial_state(
            source_text="test",
            source_language="chinese",
            novel_name="test",
            chapter_number=1,
        )
        assert isinstance(state, dict)
        assert state["source_text"] == "test"

    def test_target_language_set(self):
        state = initial_state(
            source_text="test",
            source_language="chinese",
            target_language="en",
            novel_name="test",
            chapter_number=1,
        )
        assert state["target_language"] == "en"
