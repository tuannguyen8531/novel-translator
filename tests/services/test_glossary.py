"""Tests for glossary service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.services.glossary import (
    load_glossary_data,
    clean_glossary,
    get_active_context,
    load_glossary,
    remove_glossary_term,
    save_glossary,
    save_character,
    save_character_pronoun,
    save_characters_batch,
    save_relationship,
    validate_glossary,
    load_chapter_summary,
    save_chapter_summary,
    load_chapter_summaries_recent,
    load_source_language,
    save_source_language,
    GLOSSARY_DIR,
)


class TestGlossary:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher = patch("src.services.glossary.GLOSSARY_DIR", Path(self.temp_dir.name))
        self.patcher.start()
        self.config_patcher = patch("src.services.glossary.config")
        self.mock_config = self.config_patcher.start()
        self.mock_config.novel_share_dir = ""
        self.mock_config.target_language = "vi"

    def teardown_method(self):
        self.patcher.stop()
        self.config_patcher.stop()
        self.temp_dir.cleanup()

    def test_save_and_load_glossary(self):
        save_glossary("test-novel", {"李白": "Lý Bạch"})
        result = load_glossary("test-novel")
        assert result == {"李白": "Lý Bạch"}
        assert load_glossary_data("test-novel")["terms"] == {"李白": "Lý Bạch"}

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

    def test_remove_glossary_term(self):
        save_glossary("test-novel", {"李白": "Lý Bạch", "杜甫": "Đỗ Phủ"})

        assert remove_glossary_term("test-novel", "李白")
        assert load_glossary("test-novel") == {"杜甫": "Đỗ Phủ"}

    def test_remove_missing_glossary_term(self):
        assert not remove_glossary_term("test-novel", "missing")

    def test_save_character_pronoun(self):
        save_characters_batch(
            "test-novel",
            {"李白": {"translated_name": "Lý Bạch", "role": "supporting", "pronoun": ""}},
            [],
        )

        assert save_character_pronoun("test-novel", "李白", "ông")
        data = load_glossary_data("test-novel")
        assert data["entities"]["李白"]["pronoun"] == "ông"

    def test_save_character_pronoun_missing_character(self):
        assert not save_character_pronoun("test-novel", "missing", "ông")

    def test_save_character_updates_name_and_role(self):
        save_characters_batch(
            "test-novel",
            {"李白": {"translated_name": "Lý Bạch", "role": "minor", "pronoun": ""}},
            [],
        )

        assert save_character("test-novel", "李白", translated_name="Lý Thái Bạch", role="supporting")
        data = load_glossary_data("test-novel")
        assert data["entities"]["李白"]["translated_name"] == "Lý Thái Bạch"
        assert data["entities"]["李白"]["role"] == "supporting"

    def test_save_character_accepts_legacy_name_vi_argument(self):
        save_characters_batch(
            "test-novel",
            {"李白": {"translated_name": "Lý Bạch", "role": "minor", "pronoun": ""}},
            [],
        )

        assert save_character("test-novel", "李白", name_vi="Lý Thái Bạch")
        data = load_glossary_data("test-novel")
        assert data["entities"]["李白"]["translated_name"] == "Lý Thái Bạch"
        assert "name_vi" not in data["entities"]["李白"]

    def test_save_character_missing_character(self):
        assert not save_character("test-novel", "missing", role="supporting")

    def test_save_relationship_requires_existing_characters(self):
        save_characters_batch(
            "test-novel",
            {
                "李白": {"translated_name": "Lý Bạch", "role": "supporting", "pronoun": ""},
                "杜甫": {"translated_name": "Đỗ Phủ", "role": "supporting", "pronoun": ""},
            },
            [],
        )

        assert save_relationship("test-novel", "李白", "杜甫", "friend", since_chapter=2)
        assert load_glossary_data("test-novel")["edges"] == [["李白", "杜甫", "friend", 2]]
        assert not save_relationship("test-novel", "李白", "missing", "enemy")

    def test_save_and_load_active_address_rules(self):
        save_characters_batch(
            "test-novel",
            {
                "李白": {"translated_name": "Lý Bạch", "role": "supporting", "pronoun": "ông"},
                "杜甫": {"translated_name": "Đỗ Phủ", "role": "supporting", "pronoun": "ông"},
            },
            [["李白", "杜甫", "friend"]],
            address_rules=[
                {"speaker": "Lý Bạch", "listener": "Đỗ Phủ", "self": "ta", "other": "huynh", "since": 2},
                {"speaker": "Đỗ Phủ", "listener": "Lý Bạch", "self": "tôi", "other": "ngài", "since": 5},
            ],
            chapter=2,
        )

        entities, edges, address_rules = get_active_context("test-novel", "李白 gặp 杜甫.", chapter_number=3)

        assert set(entities) == {"李白", "杜甫"}
        assert edges == [["李白", "杜甫", "friend", 2]]
        assert address_rules == [
            {"speaker": "李白", "listener": "杜甫", "self": "ta", "other": "huynh", "since": 2}
        ]

    def test_active_context_does_not_load_address_rules_for_absent_neighbors(self):
        save_characters_batch(
            "test-novel",
            {
                "陆远秋": {"translated_name": "Lục Viễn Thu", "role": "protagonist"},
                "白清夏": {"translated_name": "Bạch Thanh Hạ", "role": "supporting"},
                "梁先生": {"translated_name": "ông Lương", "role": "minor"},
            },
            [
                ["陆远秋", "白清夏", "friend"],
                ["陆远秋", "梁先生", "teacher"],
            ],
            address_rules=[
                {"speaker": "陆远秋", "listener": "白清夏", "self": "tôi", "other": "cậu", "since": 1},
                {"speaker": "陆远秋", "listener": "梁先生", "self": "cháu", "other": "ông", "since": 1},
            ],
            chapter=1,
        )

        entities, edges, address_rules = get_active_context(
            "test-novel",
            "陆远秋 gặp 白清夏.",
            chapter_number=2,
        )

        assert set(entities) == {"陆远秋", "白清夏"}
        assert edges == [["陆远秋", "白清夏", "friend", 1]]
        assert address_rules == [
            {"speaker": "陆远秋", "listener": "白清夏", "self": "tôi", "other": "cậu", "since": 1}
        ]

    def test_validate_glossary(self):
        save_glossary("test-novel", {"李白": "Lý Bạch"})

        assert validate_glossary("test-novel") == []

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

    def test_target_language_uses_separate_glossary_file(self):
        self.mock_config.target_language = "vi"
        save_glossary("test-novel", {"李白": "Lý Bạch"})

        self.mock_config.target_language = "en"
        save_glossary("test-novel", {"李白": "Li Bai"})

        assert (Path(self.temp_dir.name) / "test-novel.json").exists()
        assert (Path(self.temp_dir.name) / "test-novel.en.json").exists()

        assert load_glossary("test-novel") == {"李白": "Li Bai"}

        self.mock_config.target_language = "vi"
        assert load_glossary("test-novel") == {"李白": "Lý Bạch"}

    def test_clean_glossary_normalizes_edges_and_removes_pronoun_examples(self):
        path = Path(self.temp_dir.name) / "test-novel.json"
        path.write_text(json.dumps({
            "entities": {
                "카일": {"name_vi": "Kyle", "role": "protagonist", "pronoun": "hắn"},
                "이사벨": {"name_vi": "Isabelle", "role": "supporting", "pronoun": "cô ấy"},
            },
            "edges": [
                ["카일", "이사벨", "friend", 1],
                ["Kyle", "Isabelle", "rival", 2],
            ],
            "pronoun_examples": {"카일": ["Hắn đi."]},
        }, ensure_ascii=False), encoding="utf-8")

        stats = clean_glossary("test-novel")
        data = load_glossary_data("test-novel")

        assert stats["edges_before"] == 2
        assert stats["edges_after"] == 1
        assert stats["address_rules_before"] == 0
        assert stats["address_rules_after"] == 0
        assert stats["pronoun_examples_removed"] == 1
        assert data["entities"]["카일"]["translated_name"] == "Kyle"
        assert "name_vi" not in data["entities"]["카일"]
        assert data["edges"] == [["카일", "이사벨", "friend", 1]]
        assert "pronoun_examples" not in data


class TestGlossaryShareDir:
    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.project_glossary = self.base / "glossary"
        self.share_glossary = self.base / "share" / "my-novel"
        self.share_glossary.mkdir(parents=True)

        self.patcher_glossary_dir = patch("src.services.glossary.GLOSSARY_DIR", self.project_glossary)
        self.patcher_glossary_dir.start()

    def teardown_method(self):
        self.patcher_glossary_dir.stop()
        self.temp_dir.cleanup()

    def test_load_from_share_when_project_missing(self):
        share_file = self.share_glossary / "glossary.json"
        share_file.write_text(json.dumps({"terms": {"李白": "Lý Bạch"}}), encoding="utf-8")

        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = str(self.base / "share")
            mock_config.target_language = "vi"
            result = load_glossary("my-novel")

        assert result == {"李白": "Lý Bạch"}
        assert (self.project_glossary / "my-novel.json").exists()

    def test_project_glossary_takes_precedence_over_share(self):
        project_file = self.project_glossary / "my-novel.json"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text(json.dumps({"terms": {"杜甫": "Đỗ Phủ"}}), encoding="utf-8")

        share_file = self.share_glossary / "glossary.json"
        share_file.write_text(json.dumps({"terms": {"李白": "Lý Bạch"}}), encoding="utf-8")

        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = str(self.base / "share")
            mock_config.target_language = "vi"
            result = load_glossary("my-novel")

        assert result == {"杜甫": "Đỗ Phủ"}

    def test_no_share_dir_uses_project_only(self):
        project_file = self.project_glossary / "my-novel.json"
        project_file.parent.mkdir(parents=True, exist_ok=True)
        project_file.write_text(json.dumps({"terms": {"李白": "Lý Bạch"}}), encoding="utf-8")

        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = ""
            mock_config.target_language = "vi"
            result = load_glossary("my-novel")

        assert result == {"李白": "Lý Bạch"}

    def test_share_dir_not_set_returns_empty(self):
        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = ""
            mock_config.target_language = "vi"
            result = load_glossary("nonexistent")

        assert result == {}

    def test_save_syncs_to_share_dir(self):
        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = str(self.base / "share")
            mock_config.target_language = "vi"
            save_glossary("my-novel", {"李白": "Lý Bạch"})

        share_file = self.share_glossary / "glossary.json"
        assert share_file.exists()
        data = json.loads(share_file.read_text(encoding="utf-8"))
        assert data["terms"] == {"李白": "Lý Bạch"}

    def test_save_updates_share_on_merge(self):
        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = str(self.base / "share")
            mock_config.target_language = "vi"
            save_glossary("my-novel", {"李白": "Lý Bạch"})
            save_glossary("my-novel", {"杜甫": "Đỗ Phủ"})

        share_file = self.share_glossary / "glossary.json"
        data = json.loads(share_file.read_text(encoding="utf-8"))
        assert data["terms"] == {"李白": "Lý Bạch", "杜甫": "Đỗ Phủ"}

    def test_no_sync_when_share_dir_empty(self):
        with patch("src.services.glossary.config") as mock_config:
            mock_config.novel_share_dir = ""
            mock_config.target_language = "vi"
            save_glossary("my-novel", {"李白": "Lý Bạch"})

        share_file = self.share_glossary / "glossary.json"
        assert not share_file.exists()
