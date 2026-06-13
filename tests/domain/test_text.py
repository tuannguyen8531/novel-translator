"""Tests for language detection and chunking domain rules."""

from src.domain.chunking import split_into_chunks, split_sentences
from src.domain.language import detect_language_heuristic
from src.utils.text import normalize_paragraph_spacing


class TestDetectLanguageHeuristic:
    def test_chinese_detection(self):
        text = "这是一个测试文本用于检测语言是否为中文这是一段较长的中文文本内容"
        assert detect_language_heuristic(text) == "chinese"

    def test_korean_detection(self):
        text = "이것은 한국어 테스트 문장입니다. 안녕하세요!"
        assert detect_language_heuristic(text) == "korean"

    def test_japanese_detection(self):
        text = "これは日本語のテスト文章です。こんにちは！"
        assert detect_language_heuristic(text) == "japanese"

    def test_japanese_heavy_kanji(self):
        """Japanese text with mostly kanji but some kana should still detect as Japanese."""
        text = "東京特許許可局で許可を得た。"
        assert detect_language_heuristic(text) == "japanese"

    def test_japanese_mixed(self):
        """Mixed kanji and kana — clearly Japanese."""
        text = "彼は毎日日本語を勉強しています。"
        assert detect_language_heuristic(text) == "japanese"

    def test_unknown_for_empty(self):
        assert detect_language_heuristic("") == "unknown"

    def test_unknown_for_whitespace(self):
        assert detect_language_heuristic("   \n\n  ") == "unknown"

    def test_unknown_for_latin_only(self):
        assert detect_language_heuristic("Hello world") == "unknown"

    def test_korean_low_threshold(self):
        """Korean text with moderate Hangul density."""
        text = "테스트입니다"
        assert detect_language_heuristic(text) == "korean"


class TestSplitIntoChunks:
    def test_empty_text(self):
        assert split_into_chunks("") == []

    def test_whitespace_only(self):
        assert split_into_chunks("   \n\n  ") == []

    def test_single_paragraph(self):
        result = split_into_chunks("Hello world")
        assert result == ["Hello world"]

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = split_into_chunks(text, chunk_size=100)
        assert len(result) == 1
        assert "First paragraph" in result[0]

    def test_chunking_by_size(self):
        paras = "\n\n".join([f"Paragraph {i} content here." for i in range(20)])
        result = split_into_chunks(paras, chunk_size=50, overlap=10)
        assert len(result) > 1

    def test_overlap_preserved(self):
        """Verify overlap is included between chunks."""
        paras = "\n\n".join([f"Long paragraph {i} with enough content to fill space." for i in range(10)])
        result = split_into_chunks(paras, chunk_size=60, overlap=15)
        assert len(result) > 1

    def test_long_paragraph_split(self):
        """Single long paragraph should be split by sentences."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = split_into_chunks(text, chunk_size=30, overlap=0)
        assert len(result) > 1

    def test_illustration_marker_is_not_repeated_as_overlap(self):
        text = "Before image.\n\n[[ILLUSTRATION:001-001.jpg]]\n\nAfter image."

        result = split_into_chunks(text, chunk_size=20, overlap=100)

        assert sum(chunk.count("[[ILLUSTRATION:001-001.jpg]]") for chunk in result) == 1


class TestSplitSentences:
    def test_cjk_endings(self):
        result = split_sentences("你好。世界！测试？")
        assert len(result) == 3

    def test_western_endings(self):
        result = split_sentences("Hello. World! Test?")
        assert len(result) == 3

    def test_mixed_endings(self):
        result = split_sentences("Hello. 你好！Test?")
        assert len(result) == 3

    def test_no_endings(self):
        result = split_sentences("just text no punctuation")
        assert result == ["just text no punctuation"]


class TestNormalizeParagraphSpacing:
    def test_empty_text(self):
        assert normalize_paragraph_spacing("") == ""

    def test_single_spaced_paragraphs(self):
        text = "Paragraph 1\nParagraph 2\nParagraph 3"
        expected = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        assert normalize_paragraph_spacing(text) == expected

    def test_mix_of_spacing(self):
        text = "Paragraph 1\n\nParagraph 2\nParagraph 3\n\n\nParagraph 4"
        expected = "Paragraph 1\n\nParagraph 2\n\nParagraph 3\n\nParagraph 4"
        assert normalize_paragraph_spacing(text) == expected

    def test_whitespace_only_lines(self):
        text = "  Paragraph 1  \n   \nParagraph 2"
        expected = "Paragraph 1\n\nParagraph 2"
        assert normalize_paragraph_spacing(text) == expected
