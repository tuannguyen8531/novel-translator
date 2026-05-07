"""
LLM Service — Unified interface for AI text generation.

Supports multiple providers via raw HTTP requests:
- Ollama (local): POST /api/chat
- Gemini API: POST /v1beta/models/{model}:generateContent
- OpenRouter API: POST /api/v1/chat/completions (OpenAI-compatible)

No SDKs — all providers use httpx for HTTP calls.
"""

import json
import httpx

from src.config import config


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
        provider: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        self.provider = provider or config.llm_provider
        self.temperature = temperature if temperature is not None else config.translation_temperature
        self.max_tokens = max_tokens or config.translation_max_tokens
        self._client = httpx.Client(timeout=300.0)  # 5 min timeout for long translations

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text using the configured LLM provider."""
        if self.provider == "ollama":
            return self._generate_ollama(system_prompt, user_prompt)
        elif self.provider == "gemini":
            return self._generate_gemini(system_prompt, user_prompt)
        elif self.provider == "openrouter":
            return self._generate_openrouter(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

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

        response = self._client.post(url, json=payload)
        self._check_response(response, "Ollama")
        data = response.json()
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
                "thinkingConfig": {
                    "thinkingBudget": 0,  # Disable thinking to get clean translation output
                },
            },
        }

        response = self._client.post(url, json=payload)
        self._check_response(response, "Gemini")
        data = response.json()

        # Extract text from Gemini response
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()

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

        response = self._client.post(url, json=payload, headers=headers)
        self._check_response(response, "OpenRouter")
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")
        return choices[0]["message"]["content"].strip()

    def _check_response(self, response: httpx.Response, provider: str):
        """Check HTTP response and raise a readable error if it failed."""
        if response.is_success:
            return

        # Try to extract error message from response body
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
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Singleton instance
llm = LLMService()
