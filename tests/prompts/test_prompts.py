"""Tests for prompt template engine."""

import pytest
from src.prompts import render_prompt


class TestRenderPrompt:
    def test_render_simple_template(self):
        result = render_prompt("detector")
        assert "language detector" in result
        assert "chinese" in result
        assert "korean" in result
        assert "japanese" in result

    def test_render_with_variables(self):
        result = render_prompt("translator_system", target_language="vi", lang_name="Chinese", target_name="Vietnamese")
        assert "Chinese" in result
        assert "Vietnamese" in result
        assert "{{lang_name}}" not in result

    def test_render_with_multiple_variables(self):
        result = render_prompt(
            "learner_extract",
            target_language="vi",
            existing_terms_str="term1 → dịch 1",
            existing_chars_str="Entities:\n  李明 (Lý Minh)",
        )
        assert "term1 → dịch 1" in result
        assert "李明 (Lý Minh)" in result
        assert "{{existing_terms_str}}" not in result
        assert "{{existing_chars_str}}" not in result

    def test_render_missing_template_raises(self):
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            render_prompt("nonexistent")

    def test_render_unknown_variable_left_untouched(self):
        result = render_prompt("translator_system", target_language="vi", lang_name="Chinese", target_name="Vietnamese")
        assert "{{unknown_var}}" not in result

    def test_render_reviewer_template(self):
        result = render_prompt("reviewer", target_language="vi")
        assert "completeness" in result
        assert "naturalness" in result
        assert "consistency" in result
        assert "accuracy" in result

    def test_render_learner_summary_template(self):
        result = render_prompt("learner_summary", target_language="vi")
        assert "summary" in result.lower()
        assert "50 words" in result

    def test_render_target_specific_template(self):
        result = render_prompt("translator_system", target_language="en", lang_name="Chinese", target_name="English")
        assert "Chinese to English" in result
        assert "English translation" in result
