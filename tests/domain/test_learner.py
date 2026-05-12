"""Tests for learner node term filtering."""

from src.domain.terms import count_occurrences, filter_terms_by_frequency, MIN_TERM_FREQUENCY


class TestCountOccurrences:
    def test_basic_match(self):
        assert count_occurrences("李白 李白 李白", "李白") == 3

    def test_case_insensitive(self):
        assert count_occurrences("hello Hello HELLO", "hello") == 3

    def test_no_match(self):
        assert count_occurrences("foo bar baz", "xyz") == 0

    def test_empty_term(self):
        assert count_occurrences("some text", "") == 0

    def test_single_char_term(self):
        assert count_occurrences("a b a c a", "a") == 0  # min length 2

    def test_overlapping(self):
        assert count_occurrences("aaaa", "aa") == 2  # non-overlapping regex


class TestFilterByFrequency:
    def test_keeps_frequent_terms(self):
        text = "张三 张三 张三 李四 李四"
        terms = {"张三": "Trương Tam", "李四": "Lý Tứ"}
        result = filter_terms_by_frequency(text, terms, min_count=3)
        assert result == {"张三": "Trương Tam"}

    def test_removes_rare_terms(self):
        text = "张三 张三 张三 王五"
        terms = {"张三": "Trương Tam", "王五": "Vương Ngũ"}
        result = filter_terms_by_frequency(text, terms, min_count=3)
        assert "王五" not in result

    def test_empty_terms(self):
        result = filter_terms_by_frequency("text text text", {}, min_count=3)
        assert result == {}

    def test_default_min_frequency(self):
        text = "term " * 3 + "rare " * 1
        terms = {"term": "thuật ngữ", "rare": "hiếm"}
        result = filter_terms_by_frequency(text, terms, MIN_TERM_FREQUENCY)
        assert "term" in result
        assert "rare" not in result
