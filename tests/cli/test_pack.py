import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from pack import (
    EPUBBuilder,
    _get_default_package_dir,
    _get_novel_root_dir,
    _get_output_dir,
    _package_file_stem,
    load_metadata,
    resolve_book_author,
    resolve_book_title,
    resolve_cover_image,
)


def test_pack_output_dir_defaults_to_legacy_vietnamese_path():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = ""
        mock_config.target_language = "vi"

        assert _get_output_dir("my-novel") == Path("output") / "my-novel"


def test_pack_output_dir_uses_target_specific_english_path():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = ""
        mock_config.target_language = "vi"

        assert _get_output_dir("my-novel", "en") == Path("output") / "en" / "my-novel"


def test_pack_share_dir_uses_target_specific_output_path():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = "/share"
        mock_config.target_language = "vi"

        assert _get_output_dir("my-novel", "en") == Path("/share") / "my-novel" / "output" / "en"


def test_pack_default_package_dir_stays_outside_target_output_tree():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = ""
        mock_config.target_language = "vi"

        assert _get_default_package_dir("my-novel", "en") == Path("output")


def test_pack_default_share_package_dir_stays_outside_output_tree():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = "/share"
        mock_config.target_language = "vi"

        assert _get_default_package_dir("my-novel", "en") == Path("/share") / "my-novel"


def test_pack_file_stem_includes_target_language():
    with patch("pack.config") as mock_config:
        mock_config.target_language = "vi"

        assert _package_file_stem("my-novel") == "my-novel.vi"
        assert _package_file_stem("my-novel", "en") == "my-novel.en"


# --- _get_novel_root_dir ---


def test_novel_root_dir_with_share_dir():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = "/share"
        assert _get_novel_root_dir("my-novel") == Path("/share") / "my-novel"


def test_novel_root_dir_without_share_dir():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = ""
        assert _get_novel_root_dir("my-novel") == Path("input") / "my-novel"


# --- load_metadata ---


def test_load_metadata_reads_json(tmp_path):
    metadata = {"title": "Test Title", "author": "Author"}
    novel_dir = tmp_path / "my-novel"
    novel_dir.mkdir()
    (novel_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = str(tmp_path)
        result = load_metadata("my-novel")

    assert result == metadata


def test_load_metadata_returns_empty_dict_when_missing():
    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = "/nonexistent"
        assert load_metadata("no-such-novel") == {}


def test_load_metadata_returns_empty_dict_on_invalid_json(tmp_path):
    novel_dir = tmp_path / "my-novel"
    novel_dir.mkdir()
    (novel_dir / "metadata.json").write_text("not json", encoding="utf-8")

    with patch("pack.config") as mock_config:
        mock_config.novel_share_dir = str(tmp_path)
        assert load_metadata("my-novel") == {}


# --- resolve_book_title ---


def test_resolve_title_uses_translated_name_for_target():
    metadata = {
        "title": "原标题",
        "translated": {"vi": "Tiêu đề", "en": "English Title"},
    }
    assert resolve_book_title(metadata, "en", "fallback") == "English Title"
    assert resolve_book_title(metadata, "vi", "fallback") == "Tiêu đề"


def test_resolve_title_falls_back_to_original():
    metadata = {"title": "原标题", "translated": {}}
    assert resolve_book_title(metadata, "en", "fallback") == "原标题"


def test_resolve_title_falls_back_to_novel_name():
    assert resolve_book_title({}, "en", "my-novel") == "My Novel"


def test_resolve_title_skips_empty_translated():
    metadata = {"title": "原标题", "translated": {"en": ""}}
    assert resolve_book_title(metadata, "en", "fallback") == "原标题"


# --- resolve_book_author ---


def test_resolve_author_uses_metadata_author():
    assert resolve_book_author({"author": "Real Author"}, "AI Translator") == "Real Author"


def test_resolve_author_falls_back_when_missing_or_empty():
    assert resolve_book_author({}, "AI Translator") == "AI Translator"
    assert resolve_book_author({"author": None}, "AI Translator") == "AI Translator"
    assert resolve_book_author({"author": ""}, "AI Translator") == "AI Translator"


# --- resolve_cover_image ---


def test_resolve_cover_local_path(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xff\xd8")
    metadata = {"illustration_url": str(cover)}
    result = resolve_cover_image(metadata)
    assert result == cover


def test_resolve_cover_local_path_missing():
    metadata = {"illustration_url": "/nonexistent/cover.jpg"}
    assert resolve_cover_image(metadata) is None


def test_resolve_cover_no_url():
    assert resolve_cover_image({}) is None
    assert resolve_cover_image({"illustration_url": ""}) is None


def test_epub_builder_embeds_illustration_at_marker_position(tmp_path):
    illustrations_dir = tmp_path / "illustrations"
    illustrations_dir.mkdir()
    illustration = illustrations_dir / "001-001.jpg"
    illustration.write_bytes(b"image-data")
    output = tmp_path / "book.epub"

    builder = EPUBBuilder("Book", illustrations_dir=illustrations_dir)
    builder.add_chapter(
        "Chapter 1",
        ["Before.", "[[ILLUSTRATION:001-001.jpg]]", "After."],
    )
    builder.write(output)

    with zipfile.ZipFile(output) as epub:
        chapter = epub.read("OEBPS/chapter_1.xhtml").decode("utf-8")
        manifest = epub.read("OEBPS/content.opf").decode("utf-8")
        embedded = epub.read("OEBPS/images/001-001.jpg")

    assert chapter.index("Before.") < chapter.index("images/001-001.jpg") < chapter.index("After.")
    assert 'href="images/001-001.jpg" media-type="image/jpeg"' in manifest
    assert embedded == b"image-data"
