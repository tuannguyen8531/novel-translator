"""OpenRouter provider — OpenAI-compatible API via HTTP."""

import time

from src.config import config
from src.services.llm.base import BaseProvider


class OpenRouterProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _do_generate(self, system_prompt: str, user_prompt: str, call_type: str) -> str:
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

        start = time.monotonic()
        call_id = self._log_request_sent(
            call_type=call_type,
            url=url,
            request_body=payload,
        )
        response = self._client_instance.post(url, json=payload, headers=headers)
        duration = (time.monotonic() - start) * 1000
        self._check_response(response)
        data = response.json()

        self._log_request_received(
            call_id=call_id,
            call_type=call_type,
            url=url,
            response_body=data,
            status_code=response.status_code,
            duration_ms=duration,
        )

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {data}")
        return choices[0]["message"]["content"].strip()
