"""Tests for LLM service."""

import json
from unittest.mock import patch, MagicMock

import pytest
import httpx

from src.services.llm import get_llm, reset_llm
from src.services.llm.base import BaseProvider
from src.services.llm.ollama import OllamaProvider
from src.services.llm.gemini import GeminiProvider
from src.services.llm.openrouter import OpenRouterProvider
from src.services.llm.fallback import FallbackProvider


class TestLLMService:
    def test_provider_property_reads_config(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "gemini"
            factory_config.fallback_provider = "ollama"
            reset_llm()
            service = get_llm()
            assert isinstance(service, FallbackProvider)

            factory_config.llm_provider = "ollama"
            factory_config.fallback_provider = "gemini"
            reset_llm()
            service = get_llm()
            assert isinstance(service, FallbackProvider)

    def test_generate_unknown_provider(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "unknown"
            reset_llm()
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                get_llm()

    def _mock_httpx_post(self, mock_config, provider, response_json):
        """Helper to mock HTTP responses for LLM providers."""
        if provider == "ollama":
            mock_config.llm_provider = "ollama"
            mock_config.fallback_provider = "ollama"  # Same = no fallback wrapper
            mock_config.ollama_base_url = "http://localhost:11434"
            mock_config.ollama_model = "test-model"
        elif provider == "gemini":
            mock_config.llm_provider = "gemini"
            mock_config.fallback_provider = "gemini"
            mock_config.gemini_api_key = "test-key"
            mock_config.gemini_model = "gemini-test"
        elif provider == "openrouter":
            mock_config.llm_provider = "openrouter"
            mock_config.fallback_provider = "openrouter"
            mock_config.openrouter_api_key = "test-key"
            mock_config.openrouter_model = "test-model"

        reset_llm()
        service = get_llm()
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = response_json

        with patch("httpx.Client") as MockClient:
            MockClient.return_value.post.return_value = mock_response
            with patch("src.services.llm.base.log_api_request_sent", return_value="test-call-id"):
                with patch("src.services.llm.base.log_api_request_received"):
                    return service.generate("system", "user", "translate")

    def test_ollama_generate(self):
        with patch("src.services.llm.factory.config") as mock_config:
            result = self._mock_httpx_post(
                mock_config, "ollama",
                {"message": {"content": "translated text"}}
            )
            assert result == "translated text"

    def test_gemini_generate(self):
        with patch("src.services.llm.factory.config") as mock_config:
            result = self._mock_httpx_post(
                mock_config, "gemini",
                {"candidates": [{"content": {"parts": [{"text": "translated"}]}}]}
            )
            assert result == "translated"

    def test_gemini_missing_key(self):
        with patch("src.services.llm.gemini.config") as mock_config:
            mock_config.gemini_api_key = ""
            with patch("src.services.llm.factory.config") as factory_config:
                factory_config.llm_provider = "gemini"
                factory_config.fallback_provider = "gemini"
                reset_llm()
                service = get_llm()
                with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                    service.generate("system", "user", "translate")

    def test_openrouter_generate(self):
        with patch("src.services.llm.factory.config") as mock_config:
            result = self._mock_httpx_post(
                mock_config, "openrouter",
                {"choices": [{"message": {"content": "translated"}}]}
            )
            assert result == "translated"

    def test_check_response_error(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "ollama"
            factory_config.fallback_provider = "ollama"
            reset_llm()
            service = get_llm()
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": {"message": "bad request"}}

            with pytest.raises(RuntimeError, match="ollama API error \\(400\\)"):
                service._check_response(mock_response)

    def test_context_manager(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "ollama"
            factory_config.fallback_provider = "ollama"
            reset_llm()
            service = get_llm()
            with service as s:
                assert s is service
            assert service._client is None

    def test_get_llm_singleton(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "ollama"
            factory_config.fallback_provider = "ollama"
            reset_llm()
            llm1 = get_llm()
            llm2 = get_llm()
            assert llm1 is llm2

    def test_reset_llm(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "ollama"
            factory_config.fallback_provider = "ollama"
            reset_llm()
            llm1 = get_llm()
            reset_llm()
            llm2 = get_llm()
            assert llm1 is not llm2


class TestFallbackProvider:
    def test_fallback_on_content_block(self):
        primary = MagicMock(spec=BaseProvider)
        primary.provider_name = "gemini"
        primary.temperature = 0.3
        primary.max_tokens = 4096
        primary.generate.side_effect = RuntimeError("PROHIBITED CONTENT")

        fallback = MagicMock(spec=BaseProvider)
        fallback.provider_name = "ollama"
        fallback.generate.return_value = "fallback result"

        wrapper = FallbackProvider(primary, fallback)
        result = wrapper.generate("sys", "user", "translate")

        assert result == "fallback result"
        fallback.generate.assert_called_once_with("sys", "user", "translate")

    def test_fallback_on_no_candidates(self):
        primary = MagicMock(spec=BaseProvider)
        primary.provider_name = "gemini"
        primary.temperature = 0.3
        primary.max_tokens = 4096
        primary.generate.side_effect = RuntimeError("Gemini returned no candidates")

        fallback = MagicMock(spec=BaseProvider)
        fallback.provider_name = "ollama"
        fallback.generate.return_value = "ok"

        wrapper = FallbackProvider(primary, fallback)
        result = wrapper.generate("sys", "user", "translate")

        assert result == "ok"

    def test_fallback_on_rate_limit(self):
        primary = MagicMock(spec=BaseProvider)
        primary.provider_name = "gemini"
        primary.temperature = 0.3
        primary.max_tokens = 4096
        primary.generate.side_effect = RuntimeError("429 rate limit")

        fallback = MagicMock(spec=BaseProvider)
        fallback.provider_name = "ollama"
        fallback.generate.return_value = "ok"

        wrapper = FallbackProvider(primary, fallback)
        result = wrapper.generate("sys", "user", "translate")

        assert result == "ok"

    def test_no_fallback_on_config_error(self):
        """Config errors (missing API key) should not trigger fallback."""
        primary = MagicMock(spec=BaseProvider)
        primary.provider_name = "gemini"
        primary.temperature = 0.3
        primary.max_tokens = 4096
        primary.generate.side_effect = ValueError("GEMINI_API_KEY is not set")

        fallback = MagicMock(spec=BaseProvider)

        wrapper = FallbackProvider(primary, fallback)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            wrapper.generate("sys", "user", "translate")

        fallback.generate.assert_not_called()

    def test_fallback_factory_integration(self):
        with patch("src.services.llm.factory.config") as factory_config:
            factory_config.llm_provider = "gemini"
            factory_config.fallback_provider = "ollama"
            factory_config.gemini_api_key = "test-key"
            factory_config.gemini_model = "test"
            factory_config.ollama_base_url = "http://localhost:11434"
            factory_config.ollama_model = "test"
            reset_llm()

            service = get_llm()
            assert isinstance(service, FallbackProvider)
