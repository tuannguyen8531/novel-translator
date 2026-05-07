"""Ollama provider — local LLM via HTTP API."""

import time

from src.config import config
from src.services.llm.base import BaseProvider


class OllamaProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "ollama"

    def _do_generate(self, system_prompt: str, user_prompt: str) -> str:
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

        start = time.monotonic()
        response = self._client_instance.post(url, json=payload)
        duration = (time.monotonic() - start) * 1000
        self._check_response(response)
        data = response.json()

        self._log_request(
            url=url,
            request_body=payload,
            response_body=data,
            status_code=response.status_code,
            duration_ms=duration,
        )

        return data["message"]["content"].strip()
