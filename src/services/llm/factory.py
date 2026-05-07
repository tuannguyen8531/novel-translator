"""LLM provider factory — creates and caches the global LLM instance."""

from src.config import config
from src.services.llm.base import BaseProvider
from src.services.llm.ollama import OllamaProvider
from src.services.llm.gemini import GeminiProvider
from src.services.llm.openrouter import OpenRouterProvider

_PROVIDER_MAP: dict[str, type[BaseProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}

_llm_instance: BaseProvider | None = None


def get_llm() -> BaseProvider:
    """Get the global LLM service instance."""
    global _llm_instance
    if _llm_instance is None:
        provider_cls = _PROVIDER_MAP.get(config.llm_provider)
        if provider_cls is None:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")
        _llm_instance = provider_cls()
    return _llm_instance


def reset_llm():
    """Reset the global LLM instance (useful after config changes)."""
    global _llm_instance
    if _llm_instance is not None:
        _llm_instance.close()
    _llm_instance = None
