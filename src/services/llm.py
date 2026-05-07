"""
LLM Service — Unified interface for AI text generation.

Supports multiple providers via raw HTTP requests:
- Ollama (local): POST /api/chat
- Gemini API: POST /v1beta/models/{model}:generateContent
- OpenRouter API: POST /api/v1/chat/completions (OpenAI-compatible)

No SDKs — all providers use httpx for HTTP calls.
"""

import json
import time

import httpx

from src.config import config
from src.services.logger import log_api_request

BLOCKED_CATEGORIES = [
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
]

class LLMService:
    """
    Unified LLM service that routes to the configured provider.

    Usage:
        llm = LLMService()
        response = llm.generate(
            system_prompt="You are a translator.",
            user_prompt="Translate: 你好世界"
        )
        print(response)  # "Xin chào thế giới"
    """

    def __init__(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.temperature = temperature if temperature is not None else config.translation_temperature
        self.max_tokens = max_tokens or config.translation_max_tokens
        self._client: httpx.Client | None = None

    @property
    def provider(self) -> str:
        """Read provider from config at call time (supports runtime overrides)."""
        return config.llm_provider

    @property
    def _client_instance(self) -> httpx.Client:
        """Lazy-init HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=300.0)
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text using the configured LLM provider, with auto-retry on rate limits."""
        max_retries = 3
        backoff_delays = [5, 10, 20]  # seconds

        for attempt in range(max_retries + 1):
            try:
                return self._dispatch(system_prompt, user_prompt)
            except RuntimeError as e:
                error_msg = str(e)
                is_retryable = "429" in error_msg or "503" in error_msg or "rate" in error_msg.lower()

                if is_retryable and attempt < max_retries:
                    delay = backoff_delays[attempt]
                    print(f"  Rate limited — waiting {delay}s before retry ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                    continue
                raise

        # Should not reach here, but just in case
        return self._dispatch(system_prompt, user_prompt)

    def _dispatch(self, system_prompt: str, user_prompt: str) -> str:
        """Route to the correct provider."""
        provider = self.provider
        if provider == "ollama":
            return self._generate_ollama(system_prompt, user_prompt)
        elif provider == "gemini":
            return self._generate_gemini(system_prompt, user_prompt)
        elif provider == "openrouter":
            return self._generate_openrouter(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    def _generate_ollama(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama local API."""
        url = f"{config.ollama_base_url}/api/chat"
        payload = {
            "model": config.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        start = __import__("time").monotonic()
        response = self._client_instance.post(url, json=payload)
        duration = (__import__("time").monotonic() - start) * 1000
        self._check_response(response, "Ollama")
        data = response.json()

        log_api_request(
            call_type="ollama",
            provider="ollama",
            url=url,
            request_body=payload,
            response_body=data,
            status_code=response.status_code,
            duration_ms=duration,
        )

        return data["message"]["content"].strip()

    def _generate_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Call Google Gemini API via HTTP."""
        if not config.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{config.gemini_model}:generateContent"
            f"?key={config.gemini_api_key}"
        )
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
            "safetySettings": [
                {"category": cat, "threshold": "BLOCK_NONE"}
                for cat in BLOCKED_CATEGORIES
            ],
        }

        start = __import__("time").monotonic()
        response = self._client_instance.post(url, json=payload)
        duration = (__import__("time").monotonic() - start) * 1000
        self._check_response(response, "Gemini")
        data = response.json()

        log_api_request(
            call_type="gemini",
            provider="gemini",
            url=url.split("?")[0],  # Log URL without API key
            request_body=payload,
            response_body=data,
            status_code=response.status_code,
            duration_ms=duration,
        )

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        # Filter out thought parts (internal reasoning)
        return "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()

    def _generate_openrouter(self, system_prompt: str, user_prompt: str) -> str:
        """Call OpenRouter API (OpenAI-compatible)."""
        if not config.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in .env")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        start = __import__("time").monotonic()
        response = self._client_instance.post(url, json=payload, headers=headers)
        duration = (__import__("time").monotonic() - start) * 1000
        self._check_response(response, "OpenRouter")
        data = response.json()

        log_api_request(
            call_type="openrouter",
            provider="openrouter",
            url=url,
            request_body=payload,
            response_body=data,
            status_code=response.status_code,
            duration_ms=duration,
        )

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")
        return choices[0]["message"]["content"].strip()

    def _check_response(self, response: httpx.Response, provider: str):
        """Check HTTP response and raise a readable error if it failed."""
        if response.is_success:
            return

        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "") or str(error_data)
        except Exception:
            error_msg = response.text[:500]

        raise RuntimeError(
            f"{provider} API error ({response.status_code}): {error_msg}"
        )

    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


_llm_instance: LLMService | None = None


def get_llm() -> LLMService:
    """Get the global LLM service instance (lazy, re-created if config changes)."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService()
    return _llm_instance


def reset_llm():
    """Reset the global LLM instance (useful after config changes)."""
    global _llm_instance
    if _llm_instance is not None:
        _llm_instance.close()
    _llm_instance = None
