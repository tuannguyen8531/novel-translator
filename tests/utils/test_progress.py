"""Tests for progress tracker."""

import io
import sys
from unittest.mock import patch

from src.utils.progress import ProgressTracker


class TestProgressTracker:
    def test_start_chapter_updates_state(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            tracker = ProgressTracker(10, "test-novel")
            tracker.start_chapter(5, 3)

        assert tracker.current_chapter == 3
        output = captured.getvalue()
        assert "s total" in output
        assert "s ch" not in output

    def test_chapter_done_increments_success(self):
        tracker = ProgressTracker(10, "test-novel")
        tracker.start_chapter(1, 5)
        tracker.chapter_done(True)
        assert tracker.success == 1
        assert tracker.failed == 0

    def test_chapter_done_increments_failed(self):
        tracker = ProgressTracker(10, "test-novel")
        tracker.start_chapter(1, 5)
        tracker.chapter_done(False)
        assert tracker.success == 0
        assert tracker.failed == 1

    def test_print_summary_outputs(self):
        tracker = ProgressTracker(5, "test-novel")
        tracker.start_chapter(1, 5)
        tracker.chapter_done(True)
        tracker.start_chapter(2, 5)
        tracker.chapter_done(True)

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            tracker.print_summary()

        output = captured.getvalue()
        assert "2/5 translated" in output
        assert "test-novel" in output
