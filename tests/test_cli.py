"""Tests for CLI input path parsing and chapter scanning."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from main import parse_input_path
from translate import scan_chapters, find_untranslated


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


class TestScanChapters:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_input = Path("input")
        self.patcher = patch("translate.INPUT_DIR", Path(self.temp_dir.name))
        self.patcher.start()

    def teardown_method(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def _create_chapter(self, novel: str, num: int, content: str = "test"):
        path = Path(self.temp_dir.name) / novel / f"chapter_{num}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_scan_finds_all_chapters(self):
        self._create_chapter("my-novel", 1)
        self._create_chapter("my-novel", 2)
        self._create_chapter("my-novel", 10)
        chapters = scan_chapters("my-novel")
        assert list(chapters.keys()) == [1, 2, 10]

    def test_scan_sorted_by_number(self):
        self._create_chapter("my-novel", 5)
        self._create_chapter("my-novel", 1)
        self._create_chapter("my-novel", 3)
        chapters = scan_chapters("my-novel")
        assert list(chapters.keys()) == [1, 3, 5]

    def test_scan_ignores_non_chapter_files(self):
        (Path(self.temp_dir.name) / "my-novel").mkdir(parents=True)
        (Path(self.temp_dir.name) / "my-novel" / "notes.txt").write_text("ignore")
        (Path(self.temp_dir.name) / "my-novel" / "chapter_1.txt").write_text("keep")
        chapters = scan_chapters("my-novel")
        assert list(chapters.keys()) == [1]

    def test_scan_missing_directory(self):
        with pytest.raises(SystemExit):
            scan_chapters("nonexistent")


class TestFindUntranslated:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def teardown_method(self):
        self.temp_dir.cleanup()

    def _create_input(self, novel: str, chapters: list[int]):
        for ch in chapters:
            path = self.base / "input" / novel / f"chapter_{ch}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source", encoding="utf-8")

    def _create_output(self, novel: str, chapters: list[int]):
        for ch in chapters:
            path = self.base / "output" / novel / f"chapter_{ch:03d}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("translated", encoding="utf-8")

    def test_all_untranslated(self):
        self._create_input("my-novel", [1, 2, 3])
        chapters = {1: self.base / "input/my-novel/chapter_1.txt",
                    2: self.base / "input/my-novel/chapter_2.txt",
                    3: self.base / "input/my-novel/chapter_3.txt"}
        with patch("translate.OUTPUT_DIR", self.base / "output"):
            result = find_untranslated("my-novel", chapters)
        assert result == [1, 2, 3]

    def test_some_translated(self):
        self._create_input("my-novel", [1, 2, 3])
        self._create_output("my-novel", [1])
        chapters = {1: self.base / "input/my-novel/chapter_1.txt",
                    2: self.base / "input/my-novel/chapter_2.txt",
                    3: self.base / "input/my-novel/chapter_3.txt"}
        with patch("translate.OUTPUT_DIR", self.base / "output"):
            result = find_untranslated("my-novel", chapters)
        assert result == [2, 3]

    def test_all_translated(self):
        self._create_input("my-novel", [1, 2])
        self._create_output("my-novel", [1, 2])
        chapters = {1: self.base / "input/my-novel/chapter_1.txt",
                    2: self.base / "input/my-novel/chapter_2.txt"}
        with patch("translate.OUTPUT_DIR", self.base / "output"):
            result = find_untranslated("my-novel", chapters)
        assert result == []
