from pathlib import Path
from unittest.mock import patch

from pack import _get_default_package_dir, _get_output_dir, _package_file_stem


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
