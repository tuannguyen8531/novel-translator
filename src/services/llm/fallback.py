"""Fallback provider — wraps primary + fallback, auto-switches on failure."""

from src.services.llm.base import BaseProvider
from src.services.logger import log_error

ANSI_RESET = "\033[0m"
ANSI_YELLOW = "\033[33m"


class FallbackProvider(BaseProvider):
    """Wraps a primary and fallback provider. Tries primary first, falls back on error."""

    def __init__(self, primary: BaseProvider, fallback: BaseProvider):
        self._primary = primary
        self._fallback = fallback
        self.temperature = getattr(primary, "temperature", 0.3)
        self.max_tokens = getattr(primary, "max_tokens", 4096)
        self._client = None

    @property
    def provider_name(self) -> str:
        return f"{self._primary.provider_name}+{self._fallback.provider_name}"

    def generate(self, system_prompt: str, user_prompt: str, call_type: str) -> str:
        """Try primary provider, fall back on failure."""
        try:
            return self._primary.generate(system_prompt, user_prompt, call_type)
        except RuntimeError as e:
            error_msg = str(e)
            # Only fallback on content blocks or server errors, not config errors
            is_fallback_worthy = (
                "429" in error_msg
                or "503" in error_msg
                or "500" in error_msg
                or "rate" in error_msg.lower()
                or "internal" in error_msg.lower()
                or "no candidates" in error_msg.lower()
                or "blocked" in error_msg.lower()
                or "PROHIBITED" in error_msg.upper()
                or "content" in error_msg.lower()
            )

            if is_fallback_worthy:
                print(f"  {ANSI_YELLOW}⚠ {self._primary.provider_name} failed: {error_msg[:100]}{ANSI_RESET}")
                print(f"  {ANSI_YELLOW}  Falling back to {self._fallback.provider_name}...{ANSI_RESET}")
                log_error(
                    context="LLM Fallback Triggered",
                    error=e,
                    primary_provider=self._primary.provider_name,
                    fallback_provider=self._fallback.provider_name,
                    call_type=call_type
                )
                try:
                    return self._fallback.generate(system_prompt, user_prompt, call_type)
                except RuntimeError as fallback_err:
                    log_error(
                        context="LLM Fallback Also Failed",
                        error=fallback_err,
                        primary_provider=self._primary.provider_name,
                        fallback_provider=self._fallback.provider_name,
                        call_type=call_type
                    )
                    raise RuntimeError(
                        f"Both {self._primary.provider_name} and {self._fallback.provider_name} failed. "
                        f"Primary: {error_msg[:100]} | Fallback: {str(fallback_err)[:100]}"
                    ) from fallback_err
            raise

    def _do_generate(self, system_prompt: str, user_prompt: str, call_type: str) -> str:
        raise NotImplementedError("Use generate() instead")

    def close(self):
        self._primary.close()
        self._fallback.close()
