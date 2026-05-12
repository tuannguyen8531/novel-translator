"""Tests for configuration."""

import os
from unittest.mock import patch

from src.config import Config


class TestConfig:
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.config.load_dotenv"):
                config = Config()
                assert config.llm_provider == "ollama"
                assert config.ollama_model == "qwen3:8b"
                assert config.translation_temperature == 0.3
                assert config.chunk_size == 1500
                assert config.enable_review is False
                assert config.enable_summary is False

    def test_from_env_overrides(self):
        env = {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "CHUNK_SIZE": "2000",
            "ENABLE_REVIEW": "true",
            "ENABLE_SUMMARY": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("src.config.load_dotenv"):
                config = Config.from_env()
                assert config.llm_provider == "gemini"
                assert config.gemini_api_key == "test-key"
                assert config.chunk_size == 2000
                assert config.enable_review is True
                assert config.enable_summary is True

    def test_enable_review_variants(self):
        variants_true = ["true", "True", "TRUE", "1", "yes", "YES"]
        variants_false = ["false", "False", "0", "no", "NO", ""]

        with patch("src.config.load_dotenv"):
            for val in variants_true:
                with patch.dict(os.environ, {"ENABLE_REVIEW": val}, clear=True):
                    assert Config.from_env().enable_review is True, f"Failed for {val}"

            for val in variants_false:
                with patch.dict(os.environ, {"ENABLE_REVIEW": val}, clear=True):
                    assert Config.from_env().enable_review is False, f"Failed for {val}"

    def test_enable_summary_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.config.load_dotenv"):
                config = Config()
                assert config.enable_summary is False

    def test_enable_summary_from_env(self):
        with patch.dict(os.environ, {"ENABLE_SUMMARY": "true"}, clear=True):
            with patch("src.config.load_dotenv"):
                assert Config.from_env().enable_summary is True

    def test_fallback_provider_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.config.load_dotenv"):
                config = Config()
                assert config.fallback_provider == ""

    def test_fallback_provider_from_env(self):
        with patch.dict(os.environ, {"FALLBACK_PROVIDER": "gemini"}, clear=True):
            with patch("src.config.load_dotenv"):
                assert Config.from_env().fallback_provider == "gemini"
