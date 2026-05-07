"""Tests for graph builder logic."""

from unittest.mock import patch

from src.graph.builder import _after_review, _accept_chunk, _increment_retry, _has_more_chunks
from src.models.state import initial_state


class TestAfterReview:
    def test_score_above_threshold(self):
        with patch("src.graph.builder.config") as mock_config:
            mock_config.review_threshold = 0.7
            mock_config.max_retries = 2

            state = initial_state("text", "chinese", "novel", 1)
            state["review_score"] = 0.9
            state["retry_count"] = 0

            assert _after_review(state) == "next"

    def test_score_below_threshold(self):
        with patch("src.graph.builder.config") as mock_config:
            mock_config.review_threshold = 0.7
            mock_config.max_retries = 2

            state = initial_state("text", "chinese", "novel", 1)
            state["review_score"] = 0.5
            state["retry_count"] = 0

            assert _after_review(state) == "retry"

    def test_max_retries_exceeded(self):
        with patch("src.graph.builder.config") as mock_config:
            mock_config.review_threshold = 0.7
            mock_config.max_retries = 2

            state = initial_state("text", "chinese", "novel", 1)
            state["review_score"] = 0.5
            state["retry_count"] = 2

            assert _after_review(state) == "next"


class TestAcceptChunk:
    def test_accepts_and_increments(self):
        state = initial_state("text", "chinese", "novel", 1)
        state["translated_chunks"] = ["chunk1"]
        state["current_translation"] = "chunk2"
        state["current_chunk_index"] = 1

        result = _accept_chunk(state)

        assert result["translated_chunks"] == ["chunk1", "chunk2"]
        assert result["current_chunk_index"] == 2
        assert result["retry_count"] == 0
        assert result["review_feedback"] == ""


class TestIncrementRetry:
    def test_increments_retry(self):
        state = initial_state("text", "chinese", "novel", 1)
        state["retry_count"] = 1

        result = _increment_retry(state)
        assert result["retry_count"] == 2


class TestHasMoreChunks:
    def test_more_chunks(self):
        state = initial_state("text", "chinese", "novel", 1)
        state["chunks"] = ["c1", "c2", "c3"]
        state["current_chunk_index"] = 1

        assert _has_more_chunks(state) == "translate"

    def test_no_more_chunks(self):
        state = initial_state("text", "chinese", "novel", 1)
        state["chunks"] = ["c1", "c2"]
        state["current_chunk_index"] = 2

        assert _has_more_chunks(state) == "learn"
