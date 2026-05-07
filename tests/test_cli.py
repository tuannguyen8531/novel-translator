"""Tests for CLI input path parsing."""

import os
import tempfile
from pathlib import Path

import pytest

from main import parse_input_path


class TestParseInputPath:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def teardown_method(self):
        self.temp_dir.cleanup()

    def _create_file(self, path: str, content: str = "test"):
        full_path = Path(self.temp_dir.name) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    def test_valid_path(self):
        path = self._create_file("my-novel/chapter_1.txt")
        full, novel, chapter = parse_input_path(path)
        assert novel == "my-novel"
        assert chapter == 1

    def test_chapter_with_leading_zeros(self):
        path = self._create_file("my-novel/chapter_007.txt")
        _, novel, chapter = parse_input_path(path)
        assert novel == "my-novel"
        assert chapter == 7

    def test_large_chapter_number(self):
        path = self._create_file("novel/chapter_1234.txt")
        _, novel, chapter = parse_input_path(path)
        assert novel == "novel"
        assert chapter == 1234

    def test_nested_directory(self):
        path = self._create_file("some/deep/path/my-novel/chapter_5.txt")
        _, novel, chapter = parse_input_path(path)
        assert novel == "my-novel"
        assert chapter == 5

    def test_invalid_format_no_chapter_prefix(self):
        path = self._create_file("my-novel/ch1.txt")
        with pytest.raises(SystemExit):
            parse_input_path(path)

    def test_invalid_format_no_number(self):
        path = self._create_file("my-novel/chapter.txt")
        with pytest.raises(SystemExit):
            parse_input_path(path)

    def test_invalid_format_wrong_extension(self):
        path = self._create_file("my-novel/chapter_1.md")
        with pytest.raises(SystemExit):
            parse_input_path(path)

    def test_file_not_found(self):
        with pytest.raises(SystemExit):
            parse_input_path("nonexistent/novel/chapter_1.txt")
